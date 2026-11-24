import streamlit as st
from src.common.web_common import call,login
st.set_page_config(page_title='관리자 | 소프트웨어 배포',layout='wide')
st.title('관리자용 소프트웨어 배포 센터')
login('admin')
page=st.sidebar.radio('관리 메뉴',['대시보드','파일 등록','PC 등록','동시 배포','배포 기록'])
if page=='대시보드':
    files=call('GET','/files') or []; hosts=call('GET','/hosts') or []; jobs=call('GET','/jobs') or []
    a,b,c=st.columns(3); a.metric('등록 파일',len(files)); b.metric('등록 PC',len(hosts)); c.metric('최근 배포 작업',len(jobs))
    st.subheader('파일 목록')
    for f in files:
        st.text(f"{f['label']} | {f['filename']} | {f['size']/1024**2:.2f} MiB")
        if st.button('링크 발급',key=f['id']):
            link=call('POST',f"/files/{f['id']}/link")
            if link: st.link_button('다운로드',link['url'])
    st.subheader('등록 PC / 최근 접속(UTC)'); st.dataframe(hosts,use_container_width=True)
elif page=='파일 등록':
    with st.form('upload'):
        label=st.text_input('프로그램 이름',max_chars=100); desc=st.text_area('설명 / 버전 / 운영체제',max_chars=300)
        f=st.file_uploader('설치 파일 (최대 200 MiB)',type=['exe','msi','msix','msixbundle','zip','pdf','txt'])
        submit=st.form_submit_button('등록')
    if submit:
        if not label.strip() or f is None: st.warning('이름과 파일을 입력하세요.')
        else:
            f.seek(0); result=call('POST','/files',data={'label':label,'description':desc},files={'upload':(f.name,f,'application/octet-stream')})
            if result: st.success('등록 완료. 아직 사용자 웹에는 표시되지 않습니다. 동시 배포에서 대상 PC에 요청하세요.'); st.code(result['sha256'])
elif page=='PC 등록':
    with st.form('pc'):
        name=st.text_input('PC 이름 (예: pc01)'); submit=st.form_submit_button('등록 및 전용 키 생성')
    if submit:
        result=call('POST','/agents',json={'name':name})
        if result: st.session_state.agent_created=result
    if st.session_state.get('agent_created'):
        result=st.session_state.agent_created
        st.warning('PC 전용 키를 해당 PC 관리자에게 안전하게 전달하세요. 서버에는 해시만 저장됩니다.')
        st.code(result['name']); st.code(result['token'])
        if st.button('키 표시 닫기'): st.session_state.pop('agent_created'); st.rerun()
    st.dataframe(call('GET','/hosts') or [],use_container_width=True)
elif page=='동시 배포':
    files=call('GET','/files') or []; hosts=call('GET','/hosts') or []
    if not files or not hosts: st.info('먼저 파일과 PC를 등록하세요.'); st.stop()
    byid={f['id']:f for f in files}
    fid=st.selectbox('배포 파일',list(byid),format_func=lambda x:byid[x]['label']+' | '+byid[x]['filename'])
    targets=st.multiselect('대상 PC',[h['name'] for h in hosts],max_selections=30)
    operation=st.radio('배포 방식',['download','install_python'],format_func=lambda x: '파일 다운로드만' if x=='download' else '다운로드 + Python 자동 설치')
    if operation=='install_python':
        st.warning('Python 3.13 x64 공식 설치 파일만 지원합니다. 각 PC에서 동일한 SHA-256을 사전 승인한 에이전트가 필요합니다. 현재 사용자 계정에 설치합니다.')
        st.code(byid[fid]['sha256'])
    confirmed=st.checkbox('관리 권한이 있는 선택한 PC와 파일의 배포 방식에 동의합니다.')
    if st.button('동시 배포 요청',disabled=not targets or not confirmed):
        result=call('POST','/jobs',json={'file_id':fid,'hosts':targets,'operation':operation})
        if result: st.success('배포 요청 접수: '+result['id']+' | 선택한 PC의 사용자 웹에서 다운로드할 수 있습니다.')
else:
    st.button('새로고침')
    for j in call('GET','/jobs') or []:
        with st.expander(f"{j['status']} | {j['operation']} | {j['filename']} | {j['created_at']} UTC"):
            st.dataframe(j['tasks'],use_container_width=True)
