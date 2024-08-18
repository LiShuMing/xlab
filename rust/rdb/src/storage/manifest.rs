use super::{SegmentMeta, DeleteVectorRef, CommitEpoch};
use std::collections::HashMap;

#[derive(Debug)]
pub struct Snapshot {
    pub epoch: CommitEpoch,
    pub segments: Vec<SegmentMeta>,
    pub dvs: Vec<DeleteVectorRef>,
}

#[derive(Debug)]
pub struct Manifest {
    pub snapshots: HashMap<CommitEpoch, Snapshot>,
    pub current_epoch: CommitEpoch,
}

impl Manifest {
    pub fn new() -> Self {
        Self {
            snapshots: HashMap::new(),
            current_epoch: 0,
        }
    }
    
    pub fn create_snapshot(&mut self, segments: Vec<SegmentMeta>, dvs: Vec<DeleteVectorRef>) {
        self.current_epoch += 1;
        let snapshot = Snapshot {
            epoch: self.current_epoch,
            segments,
            dvs,
        };
        self.snapshots.insert(self.current_epoch, snapshot);
    }
    
    pub fn get_snapshot(&self, epoch: CommitEpoch) -> Option<&Snapshot> {
        self.snapshots.get(&epoch)
    }
    
    pub fn get_latest_snapshot(&self) -> Option<&Snapshot> {
        self.snapshots.get(&self.current_epoch)
    }
}