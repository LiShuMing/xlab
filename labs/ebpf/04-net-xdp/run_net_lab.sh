#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
make -s all

NS="xlab_cli"
VETH_SRV="veth_ebpf_srv"
VETH_CLI="veth_ebpf_cli"
SRV_IP="10.200.0.1"
CLI_IP="10.200.0.2"
PORT=19999

cleanup() {
    sudo ip netns del "$NS" 2>/dev/null || true
    sudo ip link del "$VETH_SRV" 2>/dev/null || true
}
trap cleanup EXIT
cleanup

sudo ip netns add "$NS"
sudo ip link add "$VETH_SRV" type veth peer name "$VETH_CLI"
sudo ip link set "$VETH_CLI" netns "$NS"
sudo ip addr add "${SRV_IP}/24" dev "$VETH_SRV"
sudo ip link set "$VETH_SRV" up
sudo ip netns exec "$NS" ip addr add "${CLI_IP}/24" dev "$VETH_CLI"
sudo ip netns exec "$NS" ip link set lo up
sudo ip netns exec "$NS" ip link set "$VETH_CLI" up

echo "================================================================"
echo "Experiment 4A: TCP Probe + Retransmit under tc netem"
echo "================================================================"

for scenario in clean netem; do
    echo ""
    echo "--- TCP Scenario: $scenario ---"
    sudo ip netns exec "$NS" tc qdisc del dev "$VETH_CLI" root 2>/dev/null || true
    if [[ "$scenario" == "netem" ]]; then
        sudo ip netns exec "$NS" tc qdisc add dev "$VETH_CLI" root netem delay 20ms 5ms loss 1%
        echo "Applied tc netem on client veth: delay 20ms 5ms loss 1%"
    fi

    sudo bpftrace -q -B line --no-warnings ./tcp_trace.bt "$PORT" >"/tmp/bt_tcp_${scenario}.log" 2>&1 &
    BT_PID=$!
    for _ in $(seq 1 60); do
        grep -q "Tracing tcp:tcp_probe" "/tmp/bt_tcp_${scenario}.log" 2>/dev/null && break
        sleep 0.1
    done

    python3 ./net_bench.py tcp-server --host "$SRV_IP" --port "$PORT" --duration 20 >/tmp/tcp_srv.log 2>&1 &
    SRV_PID=$!
    sleep 0.2

    MB=2.0
    if [[ "$scenario" == "clean" ]]; then MB=32.0; fi
    sudo ip netns exec "$NS" python3 ./net_bench.py tcp-client --host "$SRV_IP" --port "$PORT" --mb "$MB"
    wait "$SRV_PID" || true
    cat /tmp/tcp_srv.log
    rm -f /tmp/tcp_srv.log

    sleep 0.3
    sudo kill -INT "$BT_PID" 2>/dev/null || true
    wait "$BT_PID" 2>/dev/null || true
    cat "/tmp/bt_tcp_${scenario}.log"
    rm -f "/tmp/bt_tcp_${scenario}.log"
done

sudo ip netns exec "$NS" tc qdisc del dev "$VETH_CLI" root 2>/dev/null || true

echo ""
echo "================================================================"
echo "Experiment 4B: XDP (SKB mode) UDP Count / Rate-Limit / Drop"
echo "================================================================"

for mode in count ratelimit drop; do
    echo ""
    echo "--- XDP Mode: $mode (1000 UDP pkts @ 1000 pps, max_pps=200) ---"
    sudo ./bin/xdp_udp_guard --iface "$VETH_SRV" --mode "$mode" --port "$PORT" --max-pps 200 --duration 3 >"/tmp/xdp_${mode}.log" 2>&1 &
    XDP_PID=$!
    sleep 0.4

    python3 ./net_bench.py udp-server --host "$SRV_IP" --port "$PORT" --duration 2.2 >/tmp/udp_srv.log 2>&1 &
    USRV_PID=$!
    sleep 0.2

    sudo ip netns exec "$NS" python3 ./net_bench.py udp-client --host "$SRV_IP" --port "$PORT" --count 1000 --pps 1000
    wait "$USRV_PID" || true
    wait "$XDP_PID" || true

    cat /tmp/udp_srv.log
    cat "/tmp/xdp_${mode}.log"
    rm -f /tmp/udp_srv.log "/tmp/xdp_${mode}.log"
done
