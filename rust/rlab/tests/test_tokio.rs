use tokio::task;

#[tokio::test]
async fn test_basic1() {
    let join = task::spawn(async {
        // ...
        "hello world!"
    });
    // Await the result of the spawned task.
    let result = join.await.unwrap();
    assert_eq!(result, "hello world!");
}

#[test]
fn test_basic2() {
    let rt = tokio::runtime::Runtime::new().unwrap();
    rt.block_on(async {
        let join = tokio::spawn(async { 42 });
        let result = join.await.unwrap();
        assert_eq!(result, 42);
    });
}
