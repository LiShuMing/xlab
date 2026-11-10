"""调用当前源码真实算法；不申请云主机／Pod，也不启动节点。"""
from ray.autoscaler.v2.instance_manager.common import InstanceUtil
from ray.autoscaler.v2.instance_manager.config import NodeTypeConfig
from ray.autoscaler.v2.scheduler import ResourceDemandScheduler, SchedulingRequest
from ray.autoscaler.v2.schema import AutoscalerInstance
from ray.autoscaler.v2.utils import ResourceRequestUtil
from ray.core.generated.instance_manager_pb2 import Instance
from common import run


def plan(count, *, pending=0, max_nodes=3, gpu_per_request=1):
    config = NodeTypeConfig(name="gpu_worker", min_worker_nodes=0,
                           max_worker_nodes=3, resources={"CPU": 4, "GPU": 1})
    requests = [ResourceRequestUtil.make({"CPU": 1, "GPU": gpu_per_request})] * count
    instances = [AutoscalerInstance(im_instance=Instance(
        instance_id=f"pending-{i}", instance_type="gpu_worker", status=Instance.REQUESTED,
    )) for i in range(pending)]
    reply = ResourceDemandScheduler().schedule(SchedulingRequest(
        disable_launch_config_check=True, node_type_configs={"gpu_worker": config},
        max_num_nodes=max_nodes, current_instances=instances,
        resource_requests=ResourceRequestUtil.group_by_count(requests),
    ))
    return {"launch": sum(r.count for r in reply.to_launch),
            "unfulfilled": len(reply.infeasible_resource_requests)}


def experiment():
    cases = {
        "three_demands": plan(3),
        "pending_capacity": plan(1, pending=1),
        "max_nodes_two": plan(3, max_nodes=2),
        "single_request_needs_two_gpus": plan(1, gpu_per_request=2),
    }
    assert cases["three_demands"] == {"launch": 3, "unfulfilled": 0}
    assert cases["pending_capacity"] == {"launch": 0, "unfulfilled": 0}
    assert cases["max_nodes_two"] == {"launch": 2, "unfulfilled": 1}
    assert cases["single_request_needs_two_gpus"] == {"launch": 0, "unfulfilled": 1}
    instance = InstanceUtil.new_instance("lab-node", "gpu_worker", Instance.QUEUED)
    assert not InstanceUtil.set_status(instance, Instance.RAY_RUNNING)
    transitions = [Instance.QUEUED]
    for status in (Instance.REQUESTED, Instance.ALLOCATED, Instance.RAY_RUNNING,
                   Instance.RAY_STOP_REQUESTED, Instance.RAY_STOPPING,
                   Instance.RAY_STOPPED, Instance.TERMINATING, Instance.TERMINATED):
        assert InstanceUtil.set_status(instance, status)
        transitions.append(status)
    return {"scope": "真实装箱函数和状态转移规则的离线模拟，不是扩容端到端验证",
            "cases": cases,
            "transitions": [Instance.InstanceStatus.Name(s) for s in transitions],
            "illegal_transition_rejected": True}


if __name__ == "__main__":
    run(experiment)
