from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Protocol
import hashlib, time
import pandas as pd
import plotly.express as px

@dataclass(frozen=True)
class Request:
    prompt: str
    task: str
    budget: float
    latency_target_ms: int
    project_id: str

@dataclass(frozen=True)
class ModelSpec:
    name: str
    provider: str
    capabilities: tuple[str, ...]
    cost_per_1k: float
    latency_ms: int
    priority: int
    context_size: int = 16000

@dataclass(frozen=True)
class Policy:
    name: str
    max_cost: float
    allowed_models: tuple[str, ...]
    max_context: int
    rpm: int

class Provider(Protocol):
    def complete(self, request: Request, model: ModelSpec) -> dict: ...

class MockProvider:
    def complete(self, request: Request, model: ModelSpec) -> dict:
        digest = hashlib.sha256((request.prompt + model.name).encode()).hexdigest()[:10]
        return {"text": f"Mock response {digest}", "input_tokens": max(1, len(request.prompt)//4), "output_tokens": 64, "latency_ms": model.latency_ms}

class LocalProvider(MockProvider):
    pass

class OpenAICompatibleProvider(MockProvider):
    """Offline-compatible adapter boundary; external credentials are intentionally optional."""
    pass

class TokenBucket:
    def __init__(self, capacity: int, refill_per_second: float):
        self.capacity = max(1, capacity); self.tokens = float(self.capacity); self.refill = refill_per_second; self.last = time.monotonic()
    def consume(self, amount: float = 1.0) -> bool:
        now = time.monotonic(); self.tokens = min(self.capacity, self.tokens + (now-self.last)*self.refill); self.last = now
        if self.tokens >= amount: self.tokens -= amount; return True
        return False
    def remaining(self) -> float: return self.tokens

class Gateway:
    def __init__(self, models, providers, policies):
        self.models = models; self.providers = providers; self.policies = policies
        self.audit=[]; self._records=[]; self.cache={}; self.failures={}; self.buckets={}

    @classmethod
    def demo(cls):
        models=[
            ModelSpec('local-small','local',('text',),.0004,240,3,8000),
            ModelSpec('balanced','mock',('text','reasoning'),.002,480,2,16000),
            ModelSpec('vision-proxy','mock',('text','vision'),.006,900,1,32000),
        ]
        return cls(models, {'local':LocalProvider(),'mock':MockProvider()}, [Policy('demo-budget',.03,('local-small','balanced','vision-proxy'),16000,30)])

    def _policy(self, project_id: str) -> Policy:
        return self.policies[0]

    def _bucket(self, project_id: str, rpm: int) -> TokenBucket:
        if project_id not in self.buckets: self.buckets[project_id]=TokenBucket(rpm, rpm/60)
        return self.buckets[project_id]

    def route(self, req: Request) -> dict:
        policy=self._policy(req.project_id); trace=[]
        if req.budget > policy.max_cost: req=Request(req.prompt,req.task,policy.max_cost,req.latency_target_ms,req.project_id); trace.append({'stage':'policy','decision':'clamped_budget','reason':'request budget exceeded project maximum'})
        if not self._bucket(req.project_id,policy.rpm).consume():
            self.audit.append({'event':'policy_denial','reason':'rate limit','project_id':req.project_id})
            raise ValueError('Rate limit exceeded for this project.')
        candidates=[]
        for m in self.models:
            if m.name not in policy.allowed_models: trace.append({'model':m.name,'decision':'reject','reason':'model not allowed'}); continue
            if req.task not in m.capabilities: trace.append({'model':m.name,'decision':'reject','reason':'capability mismatch'}); continue
            if m.context_size > policy.max_context: trace.append({'model':m.name,'decision':'reject','reason':'context limit'}); continue
            if m.cost_per_1k > req.budget: trace.append({'model':m.name,'decision':'reject','reason':'cost exceeds budget'}); continue
            if m.latency_ms > req.latency_target_ms: trace.append({'model':m.name,'decision':'reject','reason':'latency target'}); continue
            if self.failures.get(m.name,0)>=3: trace.append({'model':m.name,'decision':'reject','reason':'circuit breaker open'}); continue
            candidates.append(m); trace.append({'model':m.name,'decision':'eligible','reason':'passes policy/capability/cost/latency'})
        if not candidates: raise ValueError('No eligible provider/model under current policy.')
        candidates.sort(key=lambda m:(m.priority,m.latency_ms,m.cost_per_1k)); start=time.perf_counter(); last_error=None
        for attempt,m in enumerate(candidates):
            try:
                provider=self.providers[m.provider]; key=hashlib.sha256((req.prompt+m.name+req.task).encode()).hexdigest()
                if key in self.cache: response=self.cache[key]|{'cache_hit':True}
                else: response=provider.complete(req,m); self.cache[key]=response; response=response|{'cache_hit':False}
                rec={'request_id':hashlib.sha256(f'{time.time_ns()}'.encode()).hexdigest()[:16],'timestamp':time.time(),'project_id':req.project_id,'model':m.name,'provider':m.provider,'latency_ms':response['latency_ms'],'input_tokens':response['input_tokens'],'output_tokens':response['output_tokens'],'estimated_cost':(response['input_tokens']+response['output_tokens'])/1000*m.cost_per_1k,'status':'success','retry_count':attempt,'fallback_used':attempt>0,'policy_decision':'allow'}
                self._records.append(rec); self.audit.append({'event':'route_decision','request_id':rec['request_id'],'trace':trace,'duration_ms':(time.perf_counter()-start)*1000}); return rec|{'trace':trace,'response':response['text']}
            except Exception as exc:
                self.failures[m.name]=self.failures.get(m.name,0)+1; last_error=exc; trace.append({'model':m.name,'decision':'runtime_failure','reason':type(exc).__name__})
        raise ValueError(f'All eligible providers failed: {last_error}')

    def records(self): return list(self._records)
    def record(self,rid): return next(r for r in self._records if r['request_id']==rid)
    def replay(self,rid):
        old=self.record(rid); return self.route(Request('replayed request','text',.03,1000,old['project_id']))
    def metrics(self):
        if not self._records:return {'requests':0,'success_rate':0,'p50_ms':0,'p95_ms':0,'p99_ms':0,'spend':0,'fallbacks':0,'cache_hit_rate':0}
        x=pd.Series([r['latency_ms'] for r in self._records]); return {'requests':len(self._records),'success_rate':sum(r['status']=='success' for r in self._records)/len(self._records),'p50_ms':x.quantile(.5),'p95_ms':x.quantile(.95),'p99_ms':x.quantile(.99),'spend':sum(r['estimated_cost'] for r in self._records),'fallbacks':sum(r['fallback_used'] for r in self._records),'cache_hit_rate':sum(1 for v in self.cache.values() if v)/max(1,len(self.cache))}
    def usage_figure(self):
        df=pd.DataFrame(self._records); return px.bar(df,x='model',y='latency_ms',title='Observed request latency') if len(df) else px.bar(title='No requests yet')
    def diagnostics(self): return {'models':len(self.models),'providers':len(self.providers),'records':len(self._records),'cache_entries':len(self.cache),'open_circuits':[k for k,v in self.failures.items() if v>=3]}
