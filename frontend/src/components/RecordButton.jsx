/**
 * RecordButton — 按住录音、松开/离开停止的圆形按钮
 *
 * 触发逻辑：
 *   onMouseDown / onTouchStart → onStart()
 *   onMouseUp   / onTouchEnd   → onStop()  （在按钮内松开）
 *   onMouseLeave               → onStop()  （鼠标移出时还在按住则停止）
 *   onTouchCancel              → onStop()  （触摸被系统中断）
 *
 * status 是唯一数据来源，按钮不自行维护"是否按下"状态。
 * doStop 内部有 isStopped 防重入保护，多路触发安全。
 */

import React from 'react'

export default function RecordButton({ status, elapsed, onStart, onStop }) {
  const isRecording  = status === 'recording'
  const isRequesting = status === 'requesting'

  function handlePointerDown(e) {
    e.preventDefault()   // 阻止移动端 touchstart → mousedown 的重复触发
    if (isRequesting || isRecording) return
    onStart()
  }

  function handleRelease(e) {
    e.preventDefault()
    if (isRecording) onStop()
  }

  const btn = {
    width:       '128px',
    height:      '128px',
    borderRadius: '50%',
    border:      'none',
    outline:     'none',
    cursor:      isRequesting ? 'not-allowed' : 'pointer',
    userSelect:  'none',
    WebkitUserSelect: 'none',
    touchAction: 'none',    // 禁用浏览器默认的滚动/缩放手势
    display:     'flex',
    flexDirection: 'column',
    alignItems:  'center',
    justifyContent: 'center',
    gap:         '6px',
    transition:  'background 0.2s, transform 0.15s, box-shadow 0.2s',
    // 颜色与缩放
    background:  isRecording  ? '#e53e3e'
               : isRequesting ? '#aaa'
               : '#4a6fa5',
    transform:   isRecording ? 'scale(1.1)' : 'scale(1)',
    boxShadow:   isRecording
      ? '0 0 0 10px rgba(229,62,62,0.18), 0 4px 16px rgba(229,62,62,0.35)'
      : '0 4px 14px rgba(74,111,165,0.35)',
    color:       '#fff',
  }

  const iconStyle  = { fontSize: '30px', lineHeight: 1, pointerEvents: 'none' }
  const labelStyle = { fontSize: '12px', fontWeight: 600, pointerEvents: 'none' }
  const timerStyle = { fontSize: '15px', fontWeight: 700, letterSpacing: '0.02em', pointerEvents: 'none' }

  function renderContent() {
    if (isRequesting) return <span style={{ fontSize: '13px' }}>请求权限…</span>
    if (isRecording) return (
      <>
        <span style={timerStyle}>{elapsed.toFixed(1)} s</span>
        <span style={{ fontSize: '11px', opacity: 0.85, pointerEvents: 'none' }}>松开结束</span>
      </>
    )
    return (
      <>
        <span style={iconStyle}>🎙</span>
        <span style={labelStyle}>按住录音</span>
      </>
    )
  }

  return (
    <button
      style={btn}
      disabled={isRequesting}
      onMouseDown={handlePointerDown}
      onMouseUp={handleRelease}
      onMouseLeave={handleRelease}
      onTouchStart={handlePointerDown}
      onTouchEnd={handleRelease}
      onTouchCancel={handleRelease}
    >
      {renderContent()}
    </button>
  )
}
