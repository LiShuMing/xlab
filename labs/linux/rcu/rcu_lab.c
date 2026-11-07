/*
 * rcu_lab.c — a userspace mirror of how the Linux RCU grace-period kthread
 * learns that "every CPU has passed a quiescent state", and of who notices a
 * CPU that never does.
 *
 * Kernel counterparts (linux 7.0.0, 1d51b370a0f8):
 *   1. self-report      rcu_qs() -> rcu_report_qs_rdp() -> rcu_report_qs_rnp()
 *                       kernel/rcu/tree_plugin.h:298, tree.c:2443, tree.c:2339
 *   2. forced QS        rcu_gp_fqs_loop() -> force_qs_rnp() ->
 *                       rcu_watching_snap_recheck() -> resched_cpu()
 *                       tree.c:2064, :2732, :855, :2783, sched/core.c:1243
 *   3. stall detection  check_cpu_stall() on the scheduler tick
 *                       tree_stall.h:772, called from rcu_pending()
 *                       tree.c:3679; prints at tree_stall.h:656
 *
 * Here a "CPU" is a pthread, a quiescent state is "this thread is not in a
 * read-side critical section and recorded that", and the forced-QS IPI is a
 * signal delivered to that thread (a signal only reaches a thread that is not
 * blocking it -- which is exactly the condition under which the kernel's
 * resched IPI also fails).
 *
 * The important structural point: the grace-period kthread never "asks" the
 * CPUs anything.  It reads a bitmap of still-outstanding CPUs; a CPU clears
 * its own bit when it passes a quiescent state.  Nobody can clear a bit for a
 * CPU that refuses to run any code -- that case is caught by a *peer CPU's*
 * timer tick, not by the kthread.
 *
 * Build:  make -C labs/linux rcu        # 产物：labs/linux/bin/rcu_lab
 * Run:    ./labs/linux/bin/rcu_lab      # all three scenarios
 */
#define _GNU_SOURCE
#include <errno.h>
#include <pthread.h>
#include <signal.h>
#include <stdarg.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#define MAX_TASKS 8

/* ---- what the kernel keeps per CPU (struct rcu_data) -------------------- */
typedef struct {
    pthread_t tid;
    const char *name;
    atomic_long qs_seq;    /* rcu_data.gp_seq: last GP this CPU reported for */
    atomic_int in_read;    /* rcu_read_lock nesting (preemptible RCU blocker) */
    atomic_int self_qs;    /* reported on its own vs. forced */
    atomic_int forced_qs;  /* reported from the signal handler */
    int mode;              /* how this "CPU" behaves */
} rcu_cpu_t;

typedef enum { NORMAL, BUSY_UNMASKED, BUSY_BLOCKED } cpu_mode_t;

typedef struct {
    int idx;
    cpu_mode_t mode;
} reader_arg_t;

static rcu_cpu_t cpus[MAX_TASKS];
static int nr_cpus;

/* ---- what the kernel keeps globally (struct rcu_state) ------------------ */
static atomic_long gp_seq;          /* current grace-period sequence */
static atomic_long force_target;    /* GP the kthread is trying to close */

static atomic_int  g_stop;
static atomic_int  g_in_gp;
static atomic_long g_gp_start;
static atomic_long g_stall_deadline; /* rcu_state.jiffies_stall */
static atomic_int  g_stall_claimed;  /* cmpxchg() winner in check_cpu_stall() */

static long        stall_ms    = 500;  /* scaled-down rcu_cpu_stall_timeout */
static long        first_fqs_ms = 50;  /* jiffies_till_first_fqs */

static volatile sig_atomic_t handler_reported[MAX_TASKS];

static long t_start;

static long now_ms(void)
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1000L + ts.tv_nsec / 1000000L;
}

static void logmsg(const char *fmt, ...)
{
    char buf[512];
    va_list ap;
    va_start(ap, fmt);
    vsnprintf(buf, sizeof(buf), fmt, ap);
    va_end(ap);
    printf("[rcu_lab %6ldms] %s\n", now_ms() - t_start, buf);
}

/* ---- the "resched_cpu() hammer": an async signal ------------------------ */
static void sigrcu_handler(int sig, siginfo_t *info, void *uc)
{
    (void)sig; (void)uc;
    int idx = (int)(intptr_t)info->si_value.sival_ptr;
    rcu_cpu_t *c = &cpus[idx];

    /*
     * A CPU inside a read-side critical section cannot pass a QS (kernel:
     * rcu_preempt_blocked_readers_cgp()).  A loop that blocks signals never
     * receives us at all -- that is the stall case.
     */
    if (atomic_load(&c->in_read) == 0) {
        long t = atomic_load(&force_target);
        long cur = atomic_load(&c->qs_seq);
        if (t > cur) {
            atomic_store(&c->qs_seq, t);
            atomic_fetch_add(&c->forced_qs, 1);
            handler_reported[idx] = 1;
        }
    }
}

/*
 * check_cpu_stall(), run from the scheduler tick of a CPU that is healthy.
 *
 * Note what this is NOT: it is not the grace-period kthread.  Every CPU's
 * tick calls rcu_pending() -> check_cpu_stall(); the first one to find
 * jiffies >= rcu_state.jiffies_stall wins a cmpxchg() and prints the report.
 * If its own bitmap bit is still set it dumps its own stack ("self-detected"),
 * otherwise it prints the *other* CPUs whose bits are still set and NMI-dumps
 * them.
 */
static void maybe_check_stall(int ticker_idx)
{
    if (!atomic_load(&g_in_gp))
        return;
    if (now_ms() < atomic_load(&g_stall_deadline))
        return;

    int expected = 0;
    if (!atomic_compare_exchange_strong(&g_stall_claimed, &expected, 1))
        return;                     /* another CPU's tick got here first */

    long target = atomic_load(&force_target);
    long gps = atomic_load(&g_gp_start);
    int self = atomic_load(&cpus[ticker_idx].qs_seq) < target;

    logmsg("  tick on %s: jiffies >= jiffies_stall -> check_cpu_stall() "
           "claims the report (self_detected=%d)", cpus[ticker_idx].name, self);
    for (int i = 0; i < nr_cpus; i++) {
        if (atomic_load(&cpus[i].qs_seq) >= target)
            continue;
        logmsg("INFO: rcu_lab detected stall on %s (g=%ld, %ld ms into GP, "
               "in_read=%d, irqs_masked=%d)", cpus[i].name, target,
               now_ms() - gps, atomic_load(&cpus[i].in_read),
               cpus[i].mode == BUSY_BLOCKED);
    }
}

/* ---- readers ------------------------------------------------------------ */
static void rcu_read_lock(int idx)  { atomic_fetch_add(&cpus[idx].in_read, 1); }
static void rcu_read_unlock(int idx)
{
    atomic_fetch_sub(&cpus[idx].in_read, 1);
    /* passing through a quiescent state: report on our own */
    long g = atomic_load(&gp_seq);
    if (g > atomic_load(&cpus[idx].qs_seq)) {
        atomic_store(&cpus[idx].qs_seq, g);
        atomic_fetch_add(&cpus[idx].self_qs, 1);
        logmsg("  %s: self-reported QS at g=%ld", cpus[idx].name, g);
    }
}

static void *reader_thread(void *arg)
{
    reader_arg_t *a = arg;
    int idx = a->idx;

    if (a->mode == BUSY_BLOCKED) {
        sigset_t set;
        sigemptyset(&set);
        sigaddset(&set, SIGRTMIN);
        pthread_sigmask(SIG_BLOCK, &set, NULL);   /* "IRQs masked" */
    }

    if (a->mode == NORMAL) {
        while (!atomic_load(&g_stop)) {
            rcu_read_lock(idx);
            usleep(2000 + idx * 1000);            /* critical section */
            rcu_read_unlock(idx);
            usleep(5000);
            maybe_check_stall(idx);               /* this CPU's tick */
        }
    } else {
        /* a long in-kernel loop with no quiescent state and no cond_resched() */
        while (!atomic_load(&g_stop))
            ;
    }
    return NULL;
}

/* ---- the grace-period kthread ------------------------------------------ */
static int gp_round(long *out_forced, long *out_stalled)
{
    long target = atomic_fetch_add(&gp_seq, 1) + 1;
    atomic_store(&force_target, target);
    for (int i = 0; i < nr_cpus; i++)
        handler_reported[i] = 0;

    long t0 = now_ms();
    long last_force_log = 0;   /* kernel: last_fqs_resched + jtsq throttle */
    int forced_this_gp = 0, fqs_round = 0;

    atomic_store(&g_gp_start, t0);
    atomic_store(&g_stall_deadline, t0 + stall_ms);
    atomic_store(&g_stall_claimed, 0);
    atomic_store(&g_in_gp, 1);
    logmsg("g=%ld GP start (bits set for all %d CPUs, stall deadline %ld ms)",
           target, nr_cpus, stall_ms);

    for (;;) {
        /* qsmask: any CPU that has not yet reported for this GP? */
        int pending = 0;
        for (int i = 0; i < nr_cpus; i++)
            if (atomic_load(&cpus[i].qs_seq) < target)
                pending++;
        if (!pending)
            break;
        if (atomic_load(&g_stall_claimed))
            break;

        /*
         * rcu_gp_fqs_loop(): sleep on a timeout (jiffies_till_first_fqs),
         * wake up, look at the bitmap, force those CPUs that are still set.
         * The kthread never blocks forever waiting for "everyone to report".
         */
        usleep((useconds_t)(fqs_round == 0 ? first_fqs_ms : 20) * 1000);
        fqs_round++;

        for (int i = 0; i < nr_cpus; i++) {
            if (atomic_load(&cpus[i].qs_seq) >= target)
                continue;
            if (handler_reported[i])
                continue;
            /*
             * rcu_watching_snap_recheck(): set rcu_urgent_qs, then (once
             * past jiffies_resched) return -1 so force_qs_rnp() runs
             * resched_cpu().  The kernel rate-limits this to once per
             * jiffies_to_sched_qs; we log at most every 200 ms so a stuck
             * CPU does not flood the console.
             */
            if (now_ms() - last_force_log >= 200) {
                logmsg("  %s: still in qsmask -> force QS (resched IPI analogue)",
                       cpus[i].name);
                last_force_log = now_ms();
            }
            union sigval sv;
            sv.sival_ptr = (void *)(intptr_t)i;
            if (pthread_sigqueue(cpus[i].tid, SIGRTMIN, sv) == 0)
                forced_this_gp++;
            else
                logmsg("  %s: cannot signal (%s) -- CPU will not be interrupted",
                       cpus[i].name, strerror(errno));
        }
    }

    atomic_store(&g_in_gp, 0);
    long dt = now_ms() - t0;
    int stalled = atomic_load(&g_stall_claimed) ? 1 : 0;
    if (!stalled) {
        logmsg("g=%ld GP end (%ld ms, forced=%d)", target, dt, forced_this_gp);
    } else {
        logmsg("g=%ld still waiting after %ld ms (forced=%d): the real GP "
               "kthread does NOT stop on a stall -- it keeps forcing until the "
               "CPU checks in or someone fixes it", target, dt, forced_this_gp);
    }

    *out_forced += forced_this_gp;
    *out_stalled += stalled;
    return stalled;
}

static void start_cpu(int idx, const char *name, cpu_mode_t mode)
{
    rcu_cpu_t *c = &cpus[idx];
    c->name = name;
    c->mode = (int)mode;
    atomic_store(&c->qs_seq, 0);
    atomic_store(&c->in_read, 0);
    atomic_store(&c->self_qs, 0);
    atomic_store(&c->forced_qs, 0);

    static reader_arg_t args[MAX_TASKS];
    args[idx].idx = idx;
    args[idx].mode = mode;
    pthread_create(&c->tid, NULL, reader_thread, &args[idx]);
}

int main(void)
{
    struct sigaction sa;
    t_start = now_ms();
    memset(&sa, 0, sizeof(sa));
    sa.sa_sigaction = sigrcu_handler;
    sa.sa_flags = SA_SIGINFO | SA_RESTART;
    sigaction(SIGRTMIN, &sa, NULL);

    logmsg("scenario A: two ordinary CPUs that report on their own");
    start_cpu(0, "cpu0", NORMAL);
    start_cpu(1, "cpu1", NORMAL);
    nr_cpus = 2;
    long forced = 0, stalled = 0;
    for (int i = 0; i < 2; i++) {
        usleep(20000);
        gp_round(&forced, &stalled);
    }
    logmsg("A done: forced=%ld stalled=%ld", forced, stalled);

    logmsg("scenario B: cpu2 spins in a QS-less loop, but signals reach it");
    start_cpu(2, "cpu2", BUSY_UNMASKED);
    nr_cpus = 3;
    forced = stalled = 0;
    gp_round(&forced, &stalled);
    logmsg("B done: forced=%ld stalled=%ld", forced, stalled);

    logmsg("scenario C: cpu3 spins with IRQs masked -> nobody can force it");
    start_cpu(3, "cpu3", BUSY_BLOCKED);
    nr_cpus = 4;
    forced = stalled = 0;
    gp_round(&forced, &stalled);
    logmsg("C done: forced=%ld stalled=%ld (this is what 'INFO: rcu detected "
           "stalls' means)", forced, stalled);

    atomic_store(&g_stop, 1);
    for (int i = 0; i < nr_cpus; i++)
        pthread_cancel(cpus[i].tid);
    for (int i = 0; i < nr_cpus; i++)
        pthread_join(cpus[i].tid, NULL);
    return 0;
}
