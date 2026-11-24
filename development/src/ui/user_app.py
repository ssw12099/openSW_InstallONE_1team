import json
import streamlit as st
import streamlit.components.v1 as components
from src.common.web_common import call, login

st.set_page_config(page_title='AI 소프트웨어 다운로드', layout='centered')
st.title('AI 소프트웨어 다운로드')
login('client')
page = st.sidebar.radio('메뉴', ['AI 다운로드', '파일 목록'])
auto = st.sidebar.checkbox('AI 응답 후 자동 다운로드 시도', value=True)
# Streamlit reruns on interactions; explicit refresh makes new admin jobs visible.
st.sidebar.button('배포 목록 새로고침')
if st.sidebar.button('채팅 초기화'):
    st.session_state.messages = []

catalog = call('GET', '/files')
if catalog is None:
    st.stop()
allowed = {f['id'] for f in catalog}
st.caption('관리자가 이 PC에 배포 요청한 파일만 표시합니다. 웹 다운로드는 에이전트 없이도 가능합니다.')


def show(m):
    with st.chat_message(m['role']):
        st.text(m['message'])
        if m.get('action') == 'download' and m.get('file', {}).get('id') in allowed:
            st.caption('파일 선택: ' + ('Ollama AI' if m.get('source') == 'ollama' else '파일명/프로그램명 검색'))
            if st.button('새 다운로드 링크 발급', key='renew_' + m['key']):
                result = call('POST', f"/files/{m['file']['id']}/link")
                if result:
                    m['url'] = result['url']
            st.link_button('파일 다운로드', m['url'])
            st.caption('10분간 유효합니다. 브라우저가 자동 다운로드를 차단하면 이 버튼을 누르세요.')


def try_browser_download(url):
    # Send the browser to the actual FileResponse, not a server-side download.
    # Attachment response may be blocked by the browser/iframe policy; link above is the fallback.
    literal = json.dumps(url).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    components.html(f'<script>window.location.assign({literal});</script>', height=1)


if not catalog:
    st.info('아직 이 PC에 배포된 파일이 없습니다. 관리자에게 배포 요청 후 배포 목록 새로고침을 누르세요.')

if page == 'AI 다운로드':
    if catalog:
        with st.expander('이 PC에 배포된 파일', expanded=True):
            for f in catalog:
                st.text(f"{f['label']} | {f['filename']}")
    st.caption('예: 파이썬 설치 파일 다운로드해 줘 / test.txt 다운로드해 줘')
    for m in st.session_state.setdefault('messages', []):
        show(m)
    prompt = st.chat_input('어떤 배포 파일이 필요하신가요?', max_chars=1000)
    if prompt:
        m = {'role':'user', 'message':prompt}
        st.session_state.messages.append(m)
        show(m)
        with st.spinner('이 PC의 배포 파일 확인 중'):
            result = call('POST', '/chat', json={'prompt':prompt})
        if result:
            m = {'role':'assistant', 'key':str(len(st.session_state.messages)), **result}
            st.session_state.messages.append(m)
            # A job may have been assigned between the initial list and chat request.
            if m.get('action') == 'download':
                allowed.add(m['file']['id'])
            show(m)
            if auto and m.get('action') == 'download':
                try_browser_download(m['url'])
else:
    for f in catalog:
        with st.container(border=True):
            st.text(f['label']+' | '+f['filename'])
            st.text(f['description'])
            st.caption(f"{f['size']/1024**2:.2f} MiB")
            if st.button('다운로드 준비 / 링크 재발급', key=f['id']):
                result = call('POST', f"/files/{f['id']}/link")
                if result:
                    st.session_state.setdefault('links', {})[f['id']] = result['url']
            if f['id'] in st.session_state.get('links', {}):
                st.link_button('파일 다운로드', st.session_state.links[f['id']])
