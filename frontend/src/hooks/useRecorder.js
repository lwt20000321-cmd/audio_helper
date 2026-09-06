/**
 * useRecorder — 录音逻辑 Hook
 *
 * 状态机：
 *   idle       初始 / 每轮录音前
 *   requesting 正在请求麦克风权限
 *   recording  录音中
 *   done       录音成功，blob 可用
 *   error      发生错误，errorMsg 有提示
 *
 * 设计原则：
 * - 用 ref（rec）集中存放所有需要在计时器回调中访问的可变值，
 *   彻底绕开 stale closure 问题。
 * - 通过 isStopped 标志防止 doStop 重入（多路触发安全）。
 * - onstop 里的时长与 mimeType 由闭包捕获，不依赖 rec.current。
 */

import { useState, useRef, useEffect } from 'react'

const MAX_DURATION_MS = 60_000   // 60 秒
const MIN_DURATION_MS = 1_000    // 1 秒
const MAX_SIZE_BYTES  = 5 * 1024 * 1024  // 5 MB

/** 按优先级检测浏览器实际支持的 MIME 类型 */
const MIME_CANDIDATES = [
  'audio/webm;codecs=opus',
  'audio/webm',
  'audio/ogg;codecs=opus',
  'audio/mp4',
]

function detectMimeType() {
  if (typeof MediaRecorder === 'undefined') return null
  for (const type of MIME_CANDIDATES) {
    if (MediaRecorder.isTypeSupported(type)) return type
  }
  return null
}

export function useRecorder() {
  const [status,    setStatus]    = useState('idle')
  const [errorMsg,  setErrorMsg]  = useState('')
  const [elapsed,   setElapsed]   = useState(0)    // 录音中实时更新；完成后为最终时长（秒）
  const [audioBlob, setAudioBlob] = useState(null)
  const [audioUrl,  setAudioUrl]  = useState(null)

  /**
   * rec.current 集中存放所有可变录音状态。
   * 计时器回调通过 rec.current 访问最新值，不依赖 React 渲染周期。
   */
  const rec = useRef({
    recorder:       null,
    stream:         null,
    displayTimer:   null,
    autoStopTimer:  null,
    isStopped:      false,
  })

  // 用于 revoke 上一次生成的 object URL
  const urlRef = useRef(null)

  // ── 内部工具（只访问 rec.current，对所有渲染快照安全）──────

  function clearTimers() {
    clearInterval(rec.current.displayTimer)
    clearTimeout(rec.current.autoStopTimer)
    rec.current.displayTimer  = null
    rec.current.autoStopTimer = null
  }

  function releaseMic() {
    const { stream } = rec.current
    if (stream) {
      stream.getTracks().forEach(t => t.stop())
      rec.current.stream = null
    }
  }

  /**
   * 停止录音（多路入口：手动松开、鼠标离开、60 s 自动、组件卸载）。
   * isStopped 确保 recorder.stop() 只调一次。
   */
  function doStop() {
    if (rec.current.isStopped) return
    rec.current.isStopped = true
    clearTimers()
    const { recorder } = rec.current
    if (recorder && recorder.state !== 'inactive') {
      recorder.stop()   // 异步触发 onstop
    } else {
      releaseMic()
    }
  }

  // ── 公开接口 ───────────────────────────────────────────────

  async function start() {
    if (status === 'requesting' || status === 'recording') return

    // 清理上一轮
    clearTimers()
    releaseMic()
    if (urlRef.current) {
      URL.revokeObjectURL(urlRef.current)
      urlRef.current = null
    }
    setAudioBlob(null)
    setAudioUrl(null)
    setElapsed(0)
    setErrorMsg('')

    // 1. 检测格式支持（用 isTypeSupported，不根据浏览器名称判断）
    const mimeType = detectMimeType()
    if (!mimeType) {
      setErrorMsg(
        '当前浏览器不支持所需录音格式（WebM/Opus 等），请使用 Chrome 或 Firefox。'
      )
      setStatus('error')
      return
    }

    // 2. 请求麦克风权限
    setStatus('requesting')
    let stream
    try {
      if (!navigator.mediaDevices?.getUserMedia) {
        throw Object.assign(new Error(), { name: 'NotSupportedError' })
      }
      stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false })
    } catch (err) {
      const denied = ['NotAllowedError', 'PermissionDeniedError', 'SecurityError']
        .includes(err.name)
      setErrorMsg(
        denied
          ? '麦克风权限被拒绝，请点击地址栏的锁形图标允许麦克风访问后刷新重试。'
          : err.name === 'NotSupportedError'
          ? '当前环境不支持录音，请确保通过 localhost 或 HTTPS 访问。'
          : '无法访问麦克风，请检查设备连接后重试。'
      )
      setStatus('error')
      return
    }

    // 3. 初始化 MediaRecorder
    let recorder
    try {
      recorder = new MediaRecorder(stream, { mimeType })
    } catch (err) {
      stream.getTracks().forEach(t => t.stop())
      setErrorMsg('录音初始化失败，请刷新页面后重试。')
      setStatus('error')
      return
    }

    // 更新 rec ref（在绑定事件前完成，确保 doStop 能拿到最新 recorder）
    rec.current.recorder  = recorder
    rec.current.stream    = stream
    rec.current.isStopped = false

    // 4. 绑定 recorder 事件
    // chunks 和 startTime 用闭包捕获，保证 onstop 回调始终引用本轮数据
    const chunks    = []
    const startTime = Date.now()
    const capturedMime = mimeType

    recorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) chunks.push(e.data)
    }

    recorder.onstop = () => {
      releaseMic()
      const durationMs = Date.now() - startTime

      // 校验最短时长
      if (durationMs < MIN_DURATION_MS) {
        setErrorMsg('录音太短（至少 1 秒），请重新按住按钮录音。')
        setStatus('error')
        setElapsed(0)
        return
      }

      const blob = new Blob(chunks, { type: capturedMime })

      // 校验文件大小
      if (blob.size > MAX_SIZE_BYTES) {
        setErrorMsg('录音文件超过 5 MB，请缩短录音时长。')
        setStatus('error')
        setElapsed(0)
        return
      }

      const url = URL.createObjectURL(blob)
      urlRef.current = url
      setAudioBlob(blob)
      setAudioUrl(url)
      setElapsed(parseFloat((durationMs / 1000).toFixed(1)))
      setStatus('done')
    }

    recorder.onerror = () => {
      clearTimers()
      releaseMic()
      setErrorMsg('录音过程中发生错误，请重试。')
      setStatus('error')
    }

    // 5. 开始录音（每 100 ms 触发一次 ondataavailable，保证 blob 完整）
    recorder.start(100)
    setStatus('recording')

    // 显示计时器（每 200 ms 刷新）
    rec.current.displayTimer = setInterval(() => {
      const s = (Date.now() - startTime) / 1000
      setElapsed(Math.min(parseFloat(s.toFixed(1)), 60))
    }, 200)

    // 60 秒自动停止
    rec.current.autoStopTimer = setTimeout(() => doStop(), MAX_DURATION_MS)
  }

  function stop() {
    doStop()
  }

  // 组件卸载时释放所有资源
  useEffect(() => {
    return () => {
      clearTimers()
      releaseMic()
      if (urlRef.current) URL.revokeObjectURL(urlRef.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return { status, errorMsg, elapsed, audioBlob, audioUrl, start, stop }
}
