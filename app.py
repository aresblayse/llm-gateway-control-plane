import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src'))
import pandas as pd
import streamlit as st
from llm_gateway_control_plane.gateway import Gateway, Request
from llm_gateway_control_plane.persistence import RequestStore

st.set_page_config(page_title='AI Gateway Control Plane',layout='wide')

def get_gateway():
    if 'gateway' not in st.session_state: st.session_state.gateway=Gateway.demo()
    return st.session_state.gateway

def main():
    g=get_gateway(); store=RequestStore(Path('data/requests.db'))
    st.title('AI Gateway Control Plane'); st.caption('Control plane · deterministic routing · policy enforcement · quotas · request observability')
    tabs=st.tabs(['Overview','Route Simulator','Models & Providers','Policies','Requests','Audit / Diagnostics'])
    with tabs[0]:
        m=g.metrics(); c=st.columns(8)
        for col,(k,v) in zip(c,[('Requests',m['requests']),('Success rate',f"{m['success_rate']:.1%}"),('p50',f"{m['p50_ms']:.0f} ms"),('p95',f"{m['p95_ms']:.0f} ms"),('p99',f"{m['p99_ms']:.0f} ms"),('Spend',f"${m['spend']:.4f}"),('Fallbacks',m['fallbacks']),('Cache hits',f"{m['cache_hit_rate']:.1%}")]): col.metric(k,v)
        st.plotly_chart(g.usage_figure(),use_container_width=True)
    with tabs[1]:
        prompt=st.text_area('Request','Summarise this quarterly report.')
        task=st.selectbox('Task type',['text','vision','reasoning']); budget=st.number_input('Max cost / request',0.0,1.0,.03,.005); latency=st.number_input('Latency target (ms)',50,5000,800,50)
        if st.button('Simulate route',type='primary'):
            try:
                result=g.route(Request(prompt=prompt,task=task,budget=budget,latency_target_ms=latency,project_id='demo')); store.save(result); st.session_state.last=result
            except ValueError as e: st.error(str(e))
        if 'last' in st.session_state:
            r=st.session_state.last; st.success(f"Selected {r['provider']} / {r['model']}")
            st.subheader('Decision trace')
            for x in r['trace']:
                st.write(f"**{x.get('model','policy')}** — {x['decision']} — {x['reason']}")
            st.json(r)
    with tabs[2]: st.dataframe(pd.DataFrame([m.__dict__ for m in g.models]),use_container_width=True,hide_index=True); st.write('Provider adapters:',', '.join(g.providers.keys()))
    with tabs[3]:
        st.dataframe(pd.DataFrame([p.__dict__ for p in g.policies]),use_container_width=True,hide_index=True)
        st.info('Demo policy: project budget, allowed-model list, context ceiling and token-bucket rate limit are enforced by the gateway.')
    with tabs[4]:
        records=g.records() or store.list(); st.dataframe(pd.DataFrame(records),use_container_width=True,hide_index=True)
        if records:
            rid=st.selectbox('Replay request',[x['request_id'] for x in records])
            if st.button('Replay through current configuration'):
                try:
                    new=g.replay(rid); st.json({'old_route':g.record(rid) if any(x['request_id']==rid for x in g.records()) else None,'new_route':new,'changed':(g.record(rid)['provider']!=new['provider']) if any(x['request_id']==rid for x in g.records()) else True})
                except ValueError as e: st.error(str(e))
    with tabs[5]:
        st.json(g.audit[-50:]); st.json(g.diagnostics()); st.download_button('Export audit JSON',json.dumps(g.audit,indent=2),'audit.json','application/json')
if __name__=='__main__': main()
