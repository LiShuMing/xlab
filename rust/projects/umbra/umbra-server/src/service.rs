use std::sync::Arc;
use tonic::{Request, Response, Status};
use umbra_core::ops::MemoryOps;
use umbra_core::types::{
    AddResult as CoreAddResult, HistoryRecord as CoreHistoryRecord, MemoryFilters,
    Message as CoreMessage, SearchResult as CoreSearchResult,
};

// Include generated proto code from the crate root
use crate::umbra_proto::{
    memory_service_server::MemoryService as MemoryServiceTrait, *,
};

pub struct UmbraMemoryService {
    ops: Arc<dyn MemoryOps>,
}

impl UmbraMemoryService {
    pub fn new(ops: Arc<dyn MemoryOps>) -> Self {
        Self { ops }
    }
}

fn to_core_message(msg: &Message) -> CoreMessage {
    CoreMessage {
        role: msg.role.clone(),
        content: msg.content.clone(),
        name: msg.name.clone(),
    }
}

fn from_core_add_result(r: CoreAddResult) -> AddResult {
    AddResult {
        id: r.id,
        memory: r.memory,
        event: r.event,
        actor_id: r.actor_id,
        role: r.role,
    }
}

fn from_core_search_result(r: CoreSearchResult) -> SearchResult {
    SearchResult {
        id: r.id,
        memory: r.memory,
        score: r.score,
        created_at: r.created_at,
        updated_at: r.updated_at,
        user_id: r.user_id,
        agent_id: r.agent_id,
        run_id: r.run_id,
        actor_id: r.actor_id,
        role: r.role,
        metadata: r.metadata,
    }
}

fn from_core_history_record(r: &CoreHistoryRecord) -> HistoryRecord {
    HistoryRecord {
        id: r.id.clone(),
        memory_id: r.memory_id.clone(),
        old_memory: r.old_memory.clone(),
        new_memory: r.new_memory.clone(),
        event: r.event.clone(),
        actor_id: r.actor_id.clone(),
        created_at: r.created_at.clone(),
        is_deleted: r.is_deleted as i32,
    }
}

#[tonic::async_trait]
impl MemoryServiceTrait for UmbraMemoryService {
    async fn add(&self, request: Request<AddRequest>) -> Result<Response<AddResponse>, Status> {
        let req = request.into_inner();
        let messages: Vec<CoreMessage> =
            req.messages.iter().map(|m| to_core_message(m)).collect();
        let filters = MemoryFilters {
            user_id: req.user_id,
            agent_id: req.agent_id,
            run_id: req.run_id,
        };
        let results = self
            .ops
            .add(messages, filters, req.metadata)
            .await
            .map_err(|e| Status::internal(e.to_string()))?;
        Ok(Response::new(AddResponse {
            results: results.into_iter().map(from_core_add_result).collect(),
        }))
    }

    async fn search(
        &self,
        request: Request<SearchRequest>,
    ) -> Result<Response<SearchResponse>, Status> {
        let req = request.into_inner();
        let filters = MemoryFilters {
            user_id: req.filters.get("user_id").cloned(),
            agent_id: req.filters.get("agent_id").cloned(),
            run_id: req.filters.get("run_id").cloned(),
        };
        let results = self
            .ops
            .search(&req.query, filters, req.top_k as usize, req.threshold, req.rerank)
            .await
            .map_err(|e| Status::internal(e.to_string()))?;
        Ok(Response::new(SearchResponse {
            results: results.into_iter().map(from_core_search_result).collect(),
        }))
    }

    async fn get(&self, request: Request<GetRequest>) -> Result<Response<GetResponse>, Status> {
        let req = request.into_inner();
        let result = self
            .ops
            .get(&req.memory_id)
            .await
            .map_err(|e| Status::internal(e.to_string()))?;
        Ok(Response::new(GetResponse {
            result: result.map(from_core_search_result),
        }))
    }

    async fn update(
        &self,
        request: Request<UpdateRequest>,
    ) -> Result<Response<UpdateResponse>, Status> {
        let req = request.into_inner();
        self.ops
            .update(&req.memory_id, &req.data)
            .await
            .map_err(|e| Status::internal(e.to_string()))?;
        Ok(Response::new(UpdateResponse {
            message: "ok".into(),
        }))
    }

    async fn delete(
        &self,
        request: Request<DeleteRequest>,
    ) -> Result<Response<DeleteResponse>, Status> {
        let req = request.into_inner();
        self.ops
            .delete(&req.memory_id)
            .await
            .map_err(|e| Status::internal(e.to_string()))?;
        Ok(Response::new(DeleteResponse {
            message: "ok".into(),
        }))
    }

    async fn delete_all(
        &self,
        request: Request<DeleteAllRequest>,
    ) -> Result<Response<DeleteAllResponse>, Status> {
        let req = request.into_inner();
        let filters = MemoryFilters {
            user_id: req.user_id,
            agent_id: req.agent_id,
            run_id: req.run_id,
        };
        let count = self
            .ops
            .delete_all(filters)
            .await
            .map_err(|e| Status::internal(e.to_string()))?;
        Ok(Response::new(DeleteAllResponse {
            deleted_count: count,
        }))
    }

    async fn get_history(
        &self,
        request: Request<GetHistoryRequest>,
    ) -> Result<Response<GetHistoryResponse>, Status> {
        let req = request.into_inner();
        let records = self
            .ops
            .get_history(&req.memory_id)
            .await
            .map_err(|e| Status::internal(e.to_string()))?;
        Ok(Response::new(GetHistoryResponse {
            records: records.iter().map(from_core_history_record).collect(),
        }))
    }
}
