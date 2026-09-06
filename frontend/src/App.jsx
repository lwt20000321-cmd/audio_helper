import React, { useState } from 'react'
import { useRecorder } from './hooks/useRecorder'
import RecordButton from './components/RecordButton'

const CITIES = ['杭州', '北京', '上海', '广州', '深圳', '成都', '武汉', '西安', '南京', '杭州']

// 去重
const CITY_OPTIONS = [...new Set(CITIES)]

function App() {
  const [city, setCity] = useState('杭州')

  const {
    status,
    errorMsg,
    elapsed,
    audioBlob,
    audioUrl,
    start,
    stop,
  } = useRecorder()

  /** 触发浏览器下载，扩展名根据实际 MIME type 决定 */
  function handleDownload() {
    if (!audioBlob || !audioUrl) return
    const mime = audioBlob.type
    const ext  = mime.includes('ogg') ? 'ogg'
               : mime.includes('mp4') ? 'm4a'
               : 'webm'
    const a = document.createElement('a')
    a.href     = audioUrl
    a.download = `recording_${Date.now()}.${ext}`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  }

  const fileSizeKB = audioBlob ? (audioBlob.size / 1024).toFixed(1) : null

  return (
    <div style={styles.page}>
      <div style={styles.card}>

        {/* ── 标题 ───────────────────────────── */}
        <h1 style={styles.title}>语音约碰面地点</h1>

        {/* ── 城市选择 ────────────────────────── */}
        <div style={styles.row}>
          <label style={styles.label}>当前城市</label>
          <select
            value={city}
            onChange={e => setCity(e.target.value)}
            style={styles.select}
          >
            {CITY_OPTIONS.map(c => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
          <span style={styles.cityNote}>（用于地址识别的默认城市）</span>
        </div>

        {/* ── 录音区域 ─────────────────────────── */}
        <div style={styles.recordArea}>
          <RecordButton
            status={status}
            elapsed={elapsed}
            onStart={start}
            onStop={stop}
          />

          <p style={styles.hint}>
            {status === 'idle'      && '按住按钮开始录音，松开结束'}
            {status === 'requesting' && '正在请求麦克风权限，请在浏览器弹窗中允许…'}
            {status === 'recording' && `录音中，松开或移出按钮即停止（最长 60 秒）`}
            {status === 'done'      &&
              `录音完成 · ${elapsed} 秒 · ${fileSizeKB} KB · 格式 ${audioBlob?.type}`}
          </p>

          {status === 'error' && errorMsg && (
            <p style={styles.error}>{errorMsg}</p>
          )}

          {/* 错误后提示可重新录音 */}
          {status === 'error' && (
            <p style={styles.retryHint}>按住按钮可重新录音</p>
          )}
        </div>

        {/* ── 试听与下载（录音成功后显示）─────── */}
        {audioUrl && status === 'done' && (
          <div style={styles.playbackArea}>
            <p style={styles.sectionTitle}>录音试听</p>
            {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
            <audio src={audioUrl} controls style={styles.audioPlayer} />

            <button onClick={handleDownload} style={styles.downloadBtn}>
              ↓ 下载录音文件（供独立测试上传接口使用）
            </button>

            <p style={styles.downloadNote}>
              文件名格式：<code>recording_[时间戳].[ext]</code>，扩展名取决于浏览器支持的格式。
            </p>
          </div>
        )}

      </div>
    </div>
  )
}

// ── 样式 ───────────────────────────────────────────────────

const styles = {
  page: {
    minHeight: '100vh',
    background: '#f0f2f5',
    display: 'flex',
    alignItems: 'flex-start',
    justifyContent: 'center',
    paddingTop: '64px',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", sans-serif',
  },
  card: {
    background: '#fff',
    borderRadius: '16px',
    padding: '36px 32px',
    width: '100%',
    maxWidth: '480px',
    boxShadow: '0 2px 20px rgba(0,0,0,0.08)',
  },
  title: {
    fontSize: '22px',
    fontWeight: 700,
    color: '#111',
    margin: '0 0 28px',
  },
  row: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    marginBottom: '32px',
    flexWrap: 'wrap',
  },
  label: {
    fontSize: '14px',
    color: '#555',
    whiteSpace: 'nowrap',
  },
  select: {
    padding: '6px 12px',
    borderRadius: '8px',
    border: '1px solid #d9d9d9',
    fontSize: '15px',
    cursor: 'pointer',
    background: '#fff',
  },
  cityNote: {
    fontSize: '12px',
    color: '#aaa',
  },
  recordArea: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '18px',
    marginBottom: '28px',
    paddingBottom: '28px',
    borderBottom: '1px solid #f0f0f0',
  },
  hint: {
    fontSize: '13px',
    color: '#888',
    textAlign: 'center',
    margin: 0,
    minHeight: '20px',
    maxWidth: '320px',
    lineHeight: 1.6,
  },
  error: {
    fontSize: '13px',
    color: '#e53e3e',
    textAlign: 'center',
    margin: 0,
    maxWidth: '360px',
    lineHeight: 1.7,
    background: '#fff5f5',
    border: '1px solid #fed7d7',
    borderRadius: '8px',
    padding: '10px 16px',
  },
  retryHint: {
    fontSize: '12px',
    color: '#aaa',
    margin: 0,
  },
  playbackArea: {
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
  },
  sectionTitle: {
    fontSize: '14px',
    fontWeight: 600,
    color: '#333',
    margin: 0,
  },
  audioPlayer: {
    width: '100%',
  },
  downloadBtn: {
    padding: '10px 16px',
    borderRadius: '8px',
    border: '1px solid #d9d9d9',
    background: '#fafafa',
    fontSize: '13px',
    cursor: 'pointer',
    color: '#333',
    textAlign: 'left',
    transition: 'background 0.15s',
  },
  downloadNote: {
    fontSize: '12px',
    color: '#aaa',
    margin: 0,
    lineHeight: 1.6,
  },
}

export default App
