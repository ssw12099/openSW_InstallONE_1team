import { useEffect, useState } from "react";
import {
  Monitor,
  LayoutDashboard,
  History,
  Settings,
  Sparkles,
  RefreshCw,
  CheckCircle2,
  Server,
  Package,
  Terminal,
  ShieldCheck,
} from "lucide-react";

import { api } from "./api";
import "./App.css";

function App() {
  const [pcs, setPcs] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [config, setConfig] = useState(null);
  const [connected, setConnected] = useState(false);

  const [request, setRequest] = useState("");
  const [plan, setPlan] = useState(null);
  const [selectedJob, setSelectedJob] = useState(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function loadData() {
    try {
      const [pcData, jobData, configData] = await Promise.all([
        api.getPCs(),
        api.getJobs(),
        api.getConfig(),
      ]);

      setPcs(pcData);
      setJobs(jobData);
      setConfig(configData);
      setConnected(true);
    } catch (err) {
      setConnected(false);
      setError(err.message);
    }
  }

  useEffect(() => {
    loadData();
  }, []);

  async function handleAnalyze() {
    if (!request.trim()) {
      setError("설치 요청을 입력해 주세요.");
      return;
    }

    setLoading(true);
    setError("");
    setMessage("");
    setPlan(null);

    try {
      const result = await api.analyze(request);
      setPlan(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleInstall() {
    if (!plan) return;

    const approved = window.confirm(
      "분석된 설치 계획을 승인하고 실행하시겠습니까?"
    );

    if (!approved) return;

    setLoading(true);
    setError("");
    setMessage("");

    try {
      const result = await api.install(plan);

      setMessage(result.message);
      setSelectedJob(result.jobs[0]);
      setPlan(null);

      await loadData();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleJobDetail(jobId) {
    setError("");

    try {
      const result = await api.getJobDetail(jobId);
      setSelectedJob(result);
    } catch (err) {
      setError(err.message);
    }
  }

  function statusLabel(status) {
    const labels = {
      simulated: "모의 완료",
      failed: "실패",
      running: "진행 중",
      pending: "대기 중",
      unknown: "연결 미확인",
      success: "성공",
      online: "온라인",
      offline: "오프라인",
    };

    return labels[status] || status;
  }

  const simulatedJobs = jobs.filter(
    (job) => job.status === "simulated"
  ).length;

  const onlinePCs = pcs.filter(
    (pc) => pc.status === "online"
  ).length;

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-icon">
            <Server size={25} />
          </div>
          <div>
            <h2>InstallONE</h2>
            <small>LAB AUTOMATION</small>
          </div>
        </div>

        <p className="menu-title">WORKSPACE</p>

        <nav>
          <a href="#dashboard">
            <LayoutDashboard size={19} />
            대시보드
          </a>

          <a href="#pcs">
            <Monitor size={19} />
            PC 관리
          </a>

          <a href="#installation">
            <Package size={19} />
            설치 관리
          </a>

          <a href="#history">
            <History size={19} />
            작업 이력
          </a>

          <a href="#settings">
            <Settings size={19} />
            환경 설정
          </a>
        </nav>

        <div className="sidebar-footer">
          <span>InstallONE v0.1.0</span>
          <small>Open Source SW · Team 1</small>
        </div>
      </aside>

      <main className="main" id="dashboard">
        <header className="header">
          <div>
            <h1>실습실 대시보드</h1>
            <p>AI 기반 개발환경 설치 및 통합 관리</p>
          </div>

          <div className="header-actions">
            <span
              className={`connection ${
                connected ? "online" : "offline"
              }`}
            >
              {connected ? "API 연결됨" : "API 연결 실패"}
            </span>

            <button
              className="secondary-button"
              onClick={loadData}
              disabled={loading}
            >
              <RefreshCw size={16} />
              새로고침
            </button>
          </div>
        </header>

        <div className="notice">
          <ShieldCheck size={19} />
          현재 프로토타입 환경입니다.
          실제 AI 호출 및 VM 설치와 모의 실행을 구분합니다.
        </div>

        <section className="stats-grid">
          <div className="stat-card">
            <Monitor size={24} />
            <p>등록된 PC</p>
            <h2>{pcs.length}대</h2>
          </div>

          <div className="stat-card">
            <Server size={24} />
            <p>온라인 PC</p>
            <h2>{onlinePCs}대</h2>
          </div>

          <div className="stat-card">
            <Package size={24} />
            <p>전체 설치 작업</p>
            <h2>{jobs.length}건</h2>
          </div>

          <div className="stat-card">
            <CheckCircle2 size={24} />
            <p>모의 완료 작업</p>
            <h2>{simulatedJobs}건</h2>
          </div>
        </section>

        {error && <div className="error-box">{error}</div>}
        {message && <div className="success-box">{message}</div>}

        <section className="panel" id="installation">
          <div className="panel-heading">
            <h2>
              <Sparkles size={22} />
              AI 설치 요청
            </h2>
            <span className="tag">
              {config?.ai_mode || "unknown"}
            </span>
          </div>

          <p className="description">
            설치할 프로그램과 대상 PC를 자연어로 입력하세요.
          </p>

          <textarea
            value={request}
            disabled={loading}
            onChange={(e) => {
              setRequest(e.target.value);
              setPlan(null);
              setMessage("");
            }}
            placeholder="예: 1번부터 4번 PC에 Python 설치해 줘"
          />

          <div className="examples">
            {[
              "전체 PC에 Git 설치해 줘",
              "2번 PC에 Java 설치해 줘",
              "1번부터 4번 PC에 Python 설치해 줘",
            ].map((example) => (
              <button
                key={example}
                disabled={loading}
                onClick={() => {
                  setRequest(example);
                  setPlan(null);
                  setMessage("");
                }}
              >
                {example}
              </button>
            ))}
          </div>

          <button
            className="primary-button"
            onClick={handleAnalyze}
            disabled={loading}
          >
            <Sparkles size={18} />
            {loading ? "처리 중..." : "설치 요청 분석"}
          </button>

          {plan && (
            <div className="plan-box">
              <h3>설치 계획 확인</h3>

              <p>대상 PC: {plan.pc_names.join(", ")}</p>

              <p>
                설치 프로그램: {plan.profile_names.join(", ")}
              </p>

              <p>분석 방식: {plan.analysis_mode}</p>
              <p>실행 방식: {config?.install_mode}</p>
              <p>작업 상태: 승인 대기</p>

              <div className="button-group">
                <button
                  className="primary-button"
                  onClick={handleInstall}
                  disabled={loading}
                >
                  설치 승인 및 실행
                </button>

                <button
                  className="secondary-button"
                  onClick={() => setPlan(null)}
                  disabled={loading}
                >
                  취소
                </button>
              </div>
            </div>
          )}
        </section>

        <section className="panel" id="pcs">
          <div className="panel-heading">
            <h2>
              <Monitor size={22} />
              실습실 PC 현황
            </h2>
            <span className="tag">{pcs.length} Devices</span>
          </div>

          <div className="pc-grid">
            {pcs.map((pc) => (
              <div className="pc-card" key={pc.id}>
                <Monitor size={36} />
                <h3>{pc.name}</h3>
                <small>{pc.os}</small>
                <small>{pc.ip_address || "IP 미등록"}</small>

                <span className={`status ${pc.status}`}>
                  {statusLabel(pc.status)}
                </span>
              </div>
            ))}
          </div>
        </section>

        <section className="panel" id="history">
          <div className="panel-heading">
            <h2>
              <History size={22} />
              설치 작업 이력
            </h2>
          </div>

          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>작업 ID</th>
                  <th>설치 프로그램</th>
                  <th>실행 방식</th>
                  <th>상태</th>
                  <th>요청 시간 (UTC)</th>
                  <th>상세</th>
                </tr>
              </thead>

              <tbody>
                {jobs.map((job) => (
                  <tr key={job.id}>
                    <td>#{job.id}</td>
                    <td>{job.profile}</td>
                    <td>{job.mode}</td>
                    <td>
                      <span className={`status ${job.status}`}>
                        {statusLabel(job.status)}
                      </span>
                    </td>
                    <td>{job.created_at}</td>
                    <td>
                      <button
                        className="secondary-button"
                        onClick={() => handleJobDetail(job.id)}
                      >
                        보기
                      </button>
                    </td>
                  </tr>
                ))}

                {jobs.length === 0 && (
                  <tr>
                    <td colSpan="6">설치 이력이 없습니다.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          {selectedJob && (
            <div className="detail-box">
              <div className="panel-heading">
                <h3>
                  <Terminal size={18} />
                  작업 #{selectedJob.id} 상세 결과
                </h3>

                <button
                  className="secondary-button"
                  onClick={() => setSelectedJob(null)}
                >
                  닫기
                </button>
              </div>

              <p>{selectedJob.request}</p>

              <p>실행 방식: {selectedJob.mode}</p>

              {selectedJob.results.length === 0 && (
                <p>저장된 PC별 결과가 없습니다.</p>
              )}

              {selectedJob.results.map((result) => (
                <div className="log-item" key={result.id}>
                  <strong>{result.pc_name}</strong>

                  <span className={`status ${result.status}`}>
                    {statusLabel(result.status)}
                  </span>

                  <p>{result.log}</p>
                  <small>
                    설치 버전: {result.installed_version || "미확인"}
                    {" · "}
                    검증: {result.verification}
                  </small>
                </div>
              ))}
            </div>
          )}
        </section>

        <section className="panel" id="settings">
          <div className="panel-heading">
            <h2>
              <Settings size={22} />
              환경 설정
            </h2>
          </div>

          <div className="setting-row">
            <span>AI 분석 방식</span>
            <strong>{config?.ai_mode || "미확인"}</strong>
          </div>

          <div className="setting-row">
            <span>설치 실행 방식</span>
            <strong>{config?.install_mode || "미확인"}</strong>
          </div>

          <div className="setting-row">
            <span>HaiGPT API 설정</span>
            <strong>
              {config
                ? config.ai_configured
                  ? "설정 완료"
                  : "미설정"
                : "미확인"}
            </strong>
          </div>
        </section>

        <footer>InstallONE · Open Source SW · Team 1</footer>
      </main>
    </div>
  );
}

export default App;