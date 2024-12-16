for i in {1..10}; do
    echo "start worker$i"
    nohup locust -f run.py --web-port=8808 --master-port=5589 --master-bind-port=5589 --worker --master-host=127.1 &
done