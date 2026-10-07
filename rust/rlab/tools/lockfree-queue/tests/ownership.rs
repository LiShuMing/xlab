use lockfree_queue::{mpmc::MpmcQueue, mpsc::MpscQueue};
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::{Arc, Mutex};
use std::thread;

struct Tracked {
    id: usize,
    drops: Arc<AtomicUsize>,
}

impl Drop for Tracked {
    fn drop(&mut self) {
        self.drops.fetch_add(1, Ordering::SeqCst);
    }
}

#[test]
fn values_are_destroyed_once_when_popped_or_left_queued() {
    let drops = Arc::new(AtomicUsize::new(0));
    {
        let queue = MpscQueue::new();
        for id in 0..100 {
            queue
                .push(Tracked {
                    id,
                    drops: drops.clone(),
                })
                .unwrap();
        }
        for id in 0..50 {
            let item = queue.pop().unwrap();
            assert_eq!(item.id, id);
        }
        assert_eq!(drops.load(Ordering::SeqCst), 50);
    }
    assert_eq!(drops.load(Ordering::SeqCst), 100);
}

#[test]
fn concurrent_consumers_receive_every_owned_value_once() {
    let drops = Arc::new(AtomicUsize::new(0));
    let queue = Arc::new(MpmcQueue::new());
    let consumed = Arc::new(Mutex::new(Vec::new()));
    for id in 0..4000 {
        queue
            .push(Tracked {
                id,
                drops: drops.clone(),
            })
            .unwrap();
    }
    let workers: Vec<_> = (0..4)
        .map(|_| {
            let queue = queue.clone();
            let consumed = consumed.clone();
            thread::spawn(move || {
                while let Ok(item) = queue.pop() {
                    consumed.lock().unwrap().push(item.id);
                }
            })
        })
        .collect();
    for worker in workers {
        worker.join().unwrap();
    }
    let mut ids = consumed.lock().unwrap();
    ids.sort_unstable();
    assert_eq!(*ids, (0..4000).collect::<Vec<_>>());
    assert_eq!(drops.load(Ordering::SeqCst), 4000);
    assert!(queue.is_empty());
}
