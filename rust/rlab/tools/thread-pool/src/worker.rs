//! Worker thread implementation

use crate::{Message, PoolError};
use std::sync::{Arc, Mutex, mpsc};
use std::thread::{self, JoinHandle};

/// A worker thread that executes tasks from a shared queue
pub struct Worker {
    /// Worker ID
    pub id: usize,
    /// Handle to the worker thread
    pub thread: Option<JoinHandle<()>>,
}

impl Worker {
    /// Spawn a new worker thread
    ///
    /// The worker will wait for tasks on the given receiver and execute them
    pub fn spawn(
        id: usize,
        receiver: Arc<Mutex<mpsc::Receiver<Message>>>,
        name_prefix: &str,
        stack_size: usize,
    ) -> Result<Self, PoolError> {
        let name = format!("{}-{}", name_prefix, id);

        let mut builder = thread::Builder::new().name(name);
        if stack_size > 0 {
            builder = builder.stack_size(stack_size);
        }

        let thread = builder
            .spawn(move || {
                Self::run(id, receiver);
            })
            .map_err(PoolError::SpawnError)?;

        Ok(Worker {
            id,
            thread: Some(thread),
        })
    }

    /// Main worker loop
    fn run(id: usize, receiver: Arc<Mutex<mpsc::Receiver<Message>>>) {
        loop {
            // Acquire lock and receive message
            let message = {
                let lock = receiver.lock();
                match lock {
                    Ok(rx) => rx.recv().ok(),
                    Err(_) => {
                        // Mutex poisoned, shut down
                        eprintln!("Worker {}: Mutex poisoned, shutting down", id);
                        break;
                    }
                }
            };

            match message {
                Some(Message::Work(task)) => {
                    task();
                }
                Some(Message::Terminate) => {
                    break;
                }
                None => {
                    // Channel closed, no more work
                    break;
                }
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicUsize, Ordering};

    #[test]
    fn test_worker_spawn() {
        let (sender, receiver) = mpsc::channel();
        let receiver = Arc::new(Mutex::new(receiver));

        let worker = Worker::spawn(0, receiver, "test", 0).unwrap();
        assert_eq!(worker.id, 0);

        // Send a task
        let counter = Arc::new(AtomicUsize::new(0));
        let counter_clone = Arc::clone(&counter);
        sender
            .send(Message::Work(Box::new(move || {
                counter_clone.fetch_add(1, Ordering::SeqCst);
            })))
            .unwrap();

        // Give time for execution
        std::thread::sleep(std::time::Duration::from_millis(50));
        assert_eq!(counter.load(Ordering::SeqCst), 1);

        // Terminate the worker
        sender.send(Message::Terminate).unwrap();
        std::thread::sleep(std::time::Duration::from_millis(50));
    }
}
