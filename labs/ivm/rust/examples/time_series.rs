use ivm_radix_lab::{
    Batch, IndexedBatch, MinValue, Minimum, SumCount, SumCountAggregator, TimeSeries,
};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut sum = TimeSeries::<SumCountAggregator>::new();
    let mut min = TimeSeries::<Minimum>::new();
    let rounds = [
        (
            "insert",
            vec![((10, 3), 2), ((10, 7), 1), ((20, -2), 1), ((30, 5), 1)],
        ),
        ("retract minimum at t=10", vec![((10, 3), -2)]),
        (
            "late correction at t=20",
            vec![((20, -2), -1), ((20, 9), 1)],
        ),
    ];
    for (label, updates) in rounds {
        let delta = Batch::from_updates(updates)?;
        let nodes = sum.apply_batch(&delta)?;
        min.apply_batch(&delta)?;
        sum.tree().validate()?;
        let (result, stats) = sum.tree().query_with_stats(0, u64::MAX)?;
        println!(
            "{label}: sum/count={result:?}, min={:?}",
            min.query(0, u64::MAX)?
        );
        println!(
            "  nodes={}, node_delta_records={}, query={stats:?}",
            sum.tree().node_count(),
            nodes.len()
        );
        // The same delta can be consumed as a grouped (prefix -> node) batch.
        let indexed = IndexedBatch::from_batch(nodes);
        let mut cursor = indexed.cursor();
        while let Some(prefix) = cursor.key() {
            while let (Some(node), Some(weight)) = (cursor.value(), cursor.weight()) {
                let cached: Vec<_> = node
                    .children
                    .iter()
                    .flatten()
                    .map(|child| child.aggregate)
                    .collect();
                println!(
                    "  prefix={:#018x}/{} node_weight={weight:+} child_caches={cached:?}",
                    prefix.key(),
                    prefix.prefix_len()
                );
                cursor.step_value();
            }
            cursor.step_key();
        }
    }
    assert_eq!(sum.query(10, 20)?, Some(SumCount { sum: 16, count: 2 }));
    assert_eq!(min.query(10, 20)?, Some(MinValue(7)));
    assert_eq!(sum.query(21, 29)?, None);
    println!("assertions passed: [10,20] sum=16 count=2 min=7; [21,29] empty");
    Ok(())
}
