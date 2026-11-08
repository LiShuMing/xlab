//! Compressed binary radix tree addressed by canonical high-bit prefixes.

use std::collections::{BTreeMap, BTreeSet};

use crate::{Batch, Error, Result};

/// Combining adjacent, ordered subtrees must be associative. There is no
/// identity requirement: absence is represented by Option, not a zero value.
pub trait Aggregate: Clone + Eq + Ord {
    fn combine(&self, other: &Self) -> Result<Self>;
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub struct Prefix {
    key: u64,
    len: u8,
}

impl Prefix {
    /// Discard suffix bits; /0 covers the full domain, /64 is a single key.
    pub fn new(key: u64, len: u8) -> Result<Self> {
        let mask = match len {
            0 => 0,
            1..=64 => u64::MAX << (64 - len),
            _ => return Err(Error::InvalidPrefix),
        };
        Ok(Self {
            key: key & mask,
            len,
        })
    }

    pub fn root() -> Self {
        Self { key: 0, len: 0 }
    }

    pub fn leaf(key: u64) -> Self {
        Self { key, len: 64 }
    }

    pub fn key(self) -> u64 {
        self.key
    }

    pub fn prefix_len(self) -> u8 {
        self.len
    }

    pub fn upper(self) -> u64 {
        match self.len {
            0 => u64::MAX,
            64 => self.key,
            _ => self.key | (u64::MAX >> self.len),
        }
    }

    pub fn contains(self, key: u64) -> bool {
        self.key <= key && key <= self.upper()
    }

    fn slot(self, key: u64) -> Result<usize> {
        if self.len == 64 || !self.contains(key) {
            return Err(Error::CorruptTree);
        }
        Ok(((key >> (63 - self.len)) & 1) as usize)
    }

    fn common(self, key: u64) -> Self {
        let len = ((self.key ^ key).leading_zeros() as u8).min(self.len);
        // len is bounded by 64, so construction cannot fail.
        Self::new(self.key, len).expect("bounded prefix length")
    }
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
pub struct Child<A> {
    pub prefix: Prefix,
    pub aggregate: A,
}

#[derive(Debug, Clone, PartialEq, Eq, PartialOrd, Ord)]
pub struct TreeNode<A> {
    pub children: [Option<Child<A>>; 2],
}

impl<A> Default for TreeNode<A> {
    fn default() -> Self {
        Self {
            children: [None, None],
        }
    }
}

impl<A: Aggregate> TreeNode<A> {
    fn aggregate(&self) -> Result<Option<A>> {
        match (&self.children[0], &self.children[1]) {
            (None, None) => Ok(None),
            (Some(child), None) | (None, Some(child)) => Ok(Some(child.aggregate.clone())),
            (Some(left), Some(right)) => Ok(Some(left.aggregate.combine(&right.aggregate)?)),
        }
    }
}

#[derive(Debug, Clone, Copy, Default, PartialEq, Eq)]
pub struct QueryStats {
    pub node_visits: usize,
    pub cached_subtrees: usize,
}

type Overlay<A> = BTreeMap<Prefix, Option<TreeNode<A>>>;
pub type NodeDelta<A> = Batch<(Prefix, TreeNode<A>)>;

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RadixTree<A> {
    nodes: BTreeMap<Prefix, TreeNode<A>>,
}

impl<A: Aggregate> Default for RadixTree<A> {
    fn default() -> Self {
        Self {
            nodes: BTreeMap::new(),
        }
    }
}

impl<A: Aggregate> RadixTree<A> {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn node_count(&self) -> usize {
        self.nodes.len()
    }

    pub fn snapshot(&self) -> NodeDelta<A> {
        Batch::from_canonical(
            self.nodes
                .iter()
                .map(|(prefix, node)| ((*prefix, node.clone()), 1))
                .collect(),
        )
    }

    fn read(&self, overlay: &Overlay<A>, prefix: Prefix) -> Result<TreeNode<A>> {
        overlay
            .get(&prefix)
            .cloned()
            .unwrap_or_else(|| self.nodes.get(&prefix).cloned())
            .ok_or(Error::CorruptTree)
    }

    /// Replace timestamp aggregates (None deletes). Duplicate timestamps use
    /// the last value in the supplied iterator. All changes commit atomically.
    pub fn apply_updates(
        &mut self,
        updates: impl IntoIterator<Item = (u64, Option<A>)>,
    ) -> Result<NodeDelta<A>> {
        let updates: BTreeMap<_, _> = updates.into_iter().collect();
        let mut overlay = Overlay::new();
        let root_prefix = Prefix::root();
        let mut root = self.nodes.get(&root_prefix).cloned().unwrap_or_default();
        for (timestamp, aggregate) in updates {
            let slot = root_prefix.slot(timestamp)?;
            root.children[slot] = self.update_child(
                root.children[slot].clone(),
                timestamp,
                aggregate,
                &mut overlay,
            )?;
        }
        // Preflight even the root aggregate: a full-range query must not fail
        // because invalid cached state was accepted during an update.
        let nonempty = root.aggregate()?.is_some();
        overlay.insert(root_prefix, nonempty.then_some(root));
        let mut delta = Vec::new();
        for (prefix, next) in &overlay {
            let old = self.nodes.get(prefix);
            if old == next.as_ref() {
                continue;
            }
            if let Some(node) = old {
                delta.push(((*prefix, node.clone()), -1));
            }
            if let Some(node) = next {
                delta.push(((*prefix, node.clone()), 1));
            }
        }
        let delta = Batch::from_updates(delta)?;
        // Nothing below this point can return an arithmetic/input error.
        for (prefix, next) in overlay {
            match next {
                Some(node) => {
                    self.nodes.insert(prefix, node);
                }
                None => {
                    self.nodes.remove(&prefix);
                }
            }
        }
        Ok(delta)
    }

    fn update_child(
        &self,
        old: Option<Child<A>>,
        timestamp: u64,
        aggregate: Option<A>,
        overlay: &mut Overlay<A>,
    ) -> Result<Option<Child<A>>> {
        let leaf = aggregate.map(|aggregate| Child {
            prefix: Prefix::leaf(timestamp),
            aggregate,
        });
        let Some(old) = old else {
            return Ok(leaf);
        };
        if !old.prefix.contains(timestamp) {
            let Some(leaf) = leaf else {
                return Ok(Some(old));
            };
            let prefix = old.prefix.common(timestamp);
            let mut node = TreeNode::default();
            let old_slot = prefix.slot(old.prefix.key)?;
            node.children[old_slot] = Some(old);
            node.children[1 - old_slot] = Some(leaf);
            let aggregate = node.aggregate()?.ok_or(Error::CorruptTree)?;
            overlay.insert(prefix, Some(node));
            return Ok(Some(Child { prefix, aggregate }));
        }
        if old.prefix.len == 64 {
            return Ok(leaf);
        }
        let prefix = old.prefix;
        let mut node = self.read(overlay, prefix)?;
        let slot = prefix.slot(timestamp)?;
        node.children[slot] = self.update_child(
            node.children[slot].clone(),
            timestamp,
            leaf.map(|child| child.aggregate),
            overlay,
        )?;
        match (&node.children[0], &node.children[1]) {
            (None, None) => {
                overlay.insert(prefix, None);
                Ok(None)
            }
            (Some(child), None) | (None, Some(child)) => {
                let child = child.clone();
                overlay.insert(prefix, None);
                Ok(Some(child))
            }
            (Some(_), Some(_)) => {
                let aggregate = node.aggregate()?.ok_or(Error::CorruptTree)?;
                overlay.insert(prefix, Some(node));
                Ok(Some(Child { prefix, aggregate }))
            }
        }
    }

    /// Closed interval [from, to]. None means no matching timestamps.
    pub fn query(&self, from: u64, to: u64) -> Result<Option<A>> {
        self.query_with_stats(from, to)
            .map(|(aggregate, _)| aggregate)
    }

    pub fn query_with_stats(&self, from: u64, to: u64) -> Result<(Option<A>, QueryStats)> {
        if from > to {
            return Err(Error::InvalidRange);
        }
        let mut stats = QueryStats::default();
        let aggregate = if self.nodes.is_empty() {
            None
        } else {
            self.query_node(Prefix::root(), from, to, &mut stats)?
        };
        Ok((aggregate, stats))
    }

    fn query_node(
        &self,
        prefix: Prefix,
        from: u64,
        to: u64,
        stats: &mut QueryStats,
    ) -> Result<Option<A>> {
        let node = self.nodes.get(&prefix).ok_or(Error::CorruptTree)?;
        stats.node_visits += 1;
        let mut result: Option<A> = None;
        for child in node.children.iter().flatten() {
            if child.prefix.upper() < from || child.prefix.key > to {
                continue;
            }
            let value = if from <= child.prefix.key && child.prefix.upper() <= to {
                stats.cached_subtrees += 1;
                Some(child.aggregate.clone())
            } else {
                self.query_node(child.prefix, from, to, stats)?
            };
            if let Some(value) = value {
                result = Some(match result {
                    None => value,
                    Some(acc) => acc.combine(&value)?,
                });
            }
        }
        Ok(result)
    }

    /// Expensive diagnostic walk, separate from the normal update path.
    pub fn validate(&self) -> Result<()> {
        if self.nodes.is_empty() {
            return Ok(());
        }
        let mut seen = BTreeSet::new();
        self.validate_node(Prefix::root(), &mut seen)?;
        if seen.len() != self.nodes.len() {
            return Err(Error::CorruptTree);
        }
        Ok(())
    }

    fn validate_node(&self, prefix: Prefix, seen: &mut BTreeSet<Prefix>) -> Result<A> {
        if !seen.insert(prefix) {
            return Err(Error::CorruptTree);
        }
        let node = self.nodes.get(&prefix).ok_or(Error::CorruptTree)?;
        if prefix != Prefix::root() && node.children.iter().flatten().count() != 2 {
            return Err(Error::CorruptTree);
        }
        for (slot, child) in node.children.iter().enumerate() {
            if let Some(child) = child {
                if child.prefix.len <= prefix.len || prefix.slot(child.prefix.key)? != slot {
                    return Err(Error::CorruptTree);
                }
                if child.prefix.len < 64
                    && self.validate_node(child.prefix, seen)? != child.aggregate
                {
                    return Err(Error::CorruptTree);
                }
            }
        }
        node.aggregate()?.ok_or(Error::CorruptTree)
    }
}
