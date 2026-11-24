import os
import requests
import streamlit as st
from src.common.config import load_config
load_config()
API=os.getenv('API_INTERNAL','http://127.0.0.1:8000').rstrip('/')

def call(method,path,**kwargs):
    try:
        r=requests.request(method,API+path,headers={'Authorization':'Bearer '+st.session_state.get('access_key',''),
            'X-PC-Name':st.session_state.get('pc_name','').strip(),
            'X-PC-Token':st.session_state.get('pc_token','')},timeout=(5,190),**kwargs)
        if not r.ok:
            st.error(str(r.json().get('detail',r.reason))); return None
        return r.json()
    except (requests.RequestException, ValueError):
        st.error('API 연결 또는 응답 오류입니다. FastAPI 실행 상태를 확인하세요.'); return None

def login(expected):
    st.sidebar.text_input('접근 키',type='password',key='access_key')
    if expected == 'client':
        st.sidebar.text_input('PC 이름 (예: pc01)',key='pc_name')
        st.sidebar.text_input('PC 전용 키',type='password',key='pc_token')
    key=st.session_state.get('access_key','')
    identity=(key, st.session_state.get('pc_name',''), st.session_state.get('pc_token',''))
    if st.session_state.get('previous_key')!=identity:
        for name in ('messages','links','agent_created'): st.session_state.pop(name,None)
        st.session_state.previous_key=identity
    if not key:
        st.info('접근 키를 입력하세요.'); st.stop()
    if expected == 'client' and not all(identity[1:]):
        st.info('관리자에게 발급받은 PC 이름과 PC 전용 키를 함께 입력하세요.'); st.stop()
    me=call('GET','/me')
    if not me: st.stop()
    if me['role']!=expected:
        st.error('이 웹에 해당하는 접근 키를 사용하세요.'); st.stop()

    if expected == 'client':
        st.sidebar.caption('배포 대상 PC: '+me['pc'])
