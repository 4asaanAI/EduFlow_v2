import React, { useState, useEffect, useRef, useMemo } from 'react';

const SPIN_KEYFRAMES = `
@keyframes tp-spin {
  to { transform: rotate(360deg); }
}
`;

function useDarkMode() {
  const [isDark, setIsDark] = useState(() => {
    const el = document.documentElement;
    return el.getAttribute('data-theme') === 'dark' || el.classList.contains('dark');
  });

  useEffect(() => {
    const observer = new MutationObserver(() => {
      const el = document.documentElement;
      setIsDark(el.getAttribute('data-theme') === 'dark' || el.classList.contains('dark'));
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class', 'data-theme'] });
    return () => observer.disconnect();
  }, []);

  return isDark;
}

function formatMs(ms) {
  if (ms == null) return '';
  if (ms < 1000) return ms + 'ms';
  return (ms / 1000).toFixed(1) + 's';
}

function buildSummary(steps, duration) {
  const parts = [];

  const searchSteps = steps.filter(s => s.step === 'searching' && s.status === 'done');
  if (searchSteps.length > 0) {
    parts.push('Searched ' + searchSteps.length + ' source' + (searchSteps.length !== 1 ? 's' : ''));
  }

  const toolDone = steps.filter(s => s.step === 'tool_done');
  const totalRecords = toolDone.reduce((sum, s) => sum + (s.count || 0), 0);
  if (totalRecords > 0) {
    parts.push('Analyzed ' + totalRecords + ' records');
  }

  const analyzeSteps = steps.filter(s => s.step === 'analyzing' && s.status === 'done');
  if (analyzeSteps.length > 0 && totalRecords === 0) {
    parts.push('Analyzed ' + analyzeSteps.length + ' step' + (analyzeSteps.length !== 1 ? 's' : ''));
  }

  if (duration != null) {
    parts.push(formatMs(duration));
  }

  return parts.length > 0 ? parts.join(' \u00b7 ') : 'Thinking completed';
}

function StepIcon({ status, isDark }) {
  const size = 16;

  if (status === 'active') {
    return (
      <div style={{
        width: size,
        height: size,
        borderRadius: '50%',
        border: '2px solid transparent',
        borderTopColor: '#4f8ff7',
        borderRightColor: '#4f8ff7',
        animation: 'tp-spin 0.7s linear infinite',
        flexShrink: 0,
      }} />
    );
  }

  if (status === 'done') {
    return (
      <span style={{
        width: size,
        height: size,
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: 12,
        fontWeight: 700,
        color: '#34d399',
        flexShrink: 0,
      }}>
        &#10003;
      </span>
    );
  }

  if (status === 'error') {
    return (
      <span style={{
        width: size,
        height: size,
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        fontSize: 12,
        fontWeight: 700,
        color: '#ef4444',
        flexShrink: 0,
      }}>
        &#10007;
      </span>
    );
  }

  // pending
  return (
    <span style={{
      width: size,
      height: size,
      display: 'inline-flex',
      alignItems: 'center',
      justifyContent: 'center',
      fontSize: 13,
      color: isDark ? '#525252' : '#a0a0a0',
      flexShrink: 0,
    }}>
      &#9675;
    </span>
  );
}

function ToolBadge({ step, isDark }) {
  if (step.step === 'tool_start') {
    return (
      <span style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 5,
        background: isDark ? 'rgba(79,143,247,0.08)' : 'rgba(79,143,247,0.06)',
        border: '1px solid ' + (isDark ? 'rgba(79,143,247,0.18)' : 'rgba(79,143,247,0.12)'),
        borderRadius: 6,
        padding: '2px 8px',
        fontSize: 11,
        color: '#4f8ff7',
        fontFamily: 'JetBrains Mono, monospace',
      }}>
        <span role="img" aria-label="tool">&#128295;</span>
        {step.tool ? 'Fetching ' + step.tool + '...' : step.message}
      </span>
    );
  }

  if (step.step === 'tool_done') {
    return (
      <span style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 5,
        background: isDark ? 'rgba(52,211,153,0.08)' : 'rgba(52,211,153,0.06)',
        border: '1px solid ' + (isDark ? 'rgba(52,211,153,0.18)' : 'rgba(52,211,153,0.12)'),
        borderRadius: 6,
        padding: '2px 8px',
        fontSize: 11,
        color: '#34d399',
        fontFamily: 'JetBrains Mono, monospace',
      }}>
        <span role="img" aria-label="tool">&#128295;</span>
        {step.tool || 'Tool'} &#10003;
        {step.count != null && (
          <span style={{ color: isDark ? '#888' : '#525252', marginLeft: 2 }}>
            ({step.count} records)
          </span>
        )}
      </span>
    );
  }

  return null;
}

function StepRow({ step, isDark, startTime }) {
  const elapsed = step.timestamp && startTime
    ? formatMs(step.timestamp - startTime)
    : '';

  const isTool = step.step === 'tool_start' || step.step === 'tool_done';

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      height: 28,
      gap: 8,
      paddingLeft: 12,
      paddingRight: 12,
      opacity: step.status === 'pending' ? 0.5 : 1,
      transition: 'opacity 0.2s ease',
    }}>
      <StepIcon status={step.status} isDark={isDark} />
      <div style={{
        flex: 1,
        fontSize: 12,
        color: step.status === 'error'
          ? '#ef4444'
          : step.status === 'active'
            ? (isDark ? '#e5e5e5' : '#171717')
            : (isDark ? '#a0a0a0' : '#525252'),
        whiteSpace: 'nowrap',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        lineHeight: '28px',
      }}>
        {isTool ? <ToolBadge step={step} isDark={isDark} /> : step.message}
      </div>
      {elapsed && (
        <span style={{
          fontSize: 11,
          color: isDark ? '#525252' : '#a0a0a0',
          fontFamily: 'JetBrains Mono, monospace',
          flexShrink: 0,
        }}>
          {elapsed}
        </span>
      )}
    </div>
  );
}

export default function ThinkingProcess({ steps, isStreaming, collapsed, duration }) {
  const isDark = useDarkMode();
  const [userExpanded, setUserExpanded] = useState(false);
  const contentRef = useRef(null);
  const [contentHeight, setContentHeight] = useState('auto');
  const styleInjected = useRef(false);

  // Inject keyframes once
  useEffect(() => {
    if (styleInjected.current) return;
    styleInjected.current = true;
    const style = document.createElement('style');
    style.textContent = SPIN_KEYFRAMES;
    document.head.appendChild(style);
    return () => { document.head.removeChild(style); };
  }, []);

  // Measure content for smooth height transitions
  useEffect(() => {
    if (contentRef.current) {
      setContentHeight(contentRef.current.scrollHeight + 'px');
    }
  }, [steps]);

  // Reset user override when streaming state changes
  useEffect(() => {
    setUserExpanded(false);
  }, [isStreaming]);

  const isExpanded = collapsed ? userExpanded : true;

  const startTime = useMemo(() => {
    if (!steps || steps.length === 0) return null;
    return steps.reduce((min, s) => {
      if (s.timestamp && (min === null || s.timestamp < min)) return s.timestamp;
      return min;
    }, null);
  }, [steps]);

  const summaryText = useMemo(() => {
    return buildSummary(steps || [], duration);
  }, [steps, duration]);

  // HIDDEN: Don't render if steps array is empty or absent
  if (!steps || steps.length === 0) return null;

  const borderColor = '#4f8ff7';

  return (
    <div style={{
      borderLeft: '2px solid ' + borderColor,
      marginBottom: 8,
      borderRadius: '0 8px 8px 0',
      background: isDark ? 'rgba(79,143,247,0.03)' : 'rgba(79,143,247,0.02)',
      overflow: 'hidden',
      transition: 'all 0.3s ease',
    }}>
      {/* Collapsed summary bar */}
      {collapsed && (
        <div
          onClick={() => setUserExpanded(prev => !prev)}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setUserExpanded(prev => !prev); } }}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '6px 12px',
            cursor: 'pointer',
            userSelect: 'none',
            fontSize: 12,
            color: isDark ? '#888' : '#525252',
            transition: 'background 0.15s ease',
          }}
          onMouseEnter={(e) => { e.currentTarget.style.background = isDark ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.02)'; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
        >
          <span style={{
            display: 'inline-block',
            fontSize: 10,
            transition: 'transform 0.2s ease',
            transform: isExpanded ? 'rotate(90deg)' : 'rotate(0deg)',
          }}>
            &#9654;
          </span>
          <span>{summaryText}</span>
        </div>
      )}

      {/* Expanded step list */}
      <div
        ref={contentRef}
        style={{
          maxHeight: isExpanded ? contentHeight : '0px',
          opacity: isExpanded ? 1 : 0,
          overflow: 'hidden',
          transition: 'max-height 0.3s ease, opacity 0.2s ease',
          paddingTop: isExpanded ? 4 : 0,
          paddingBottom: isExpanded ? 4 : 0,
        }}
      >
        {steps.map((step, i) => (
          <StepRow
            key={step.step + '-' + i}
            step={step}
            isDark={isDark}
            startTime={startTime}
          />
        ))}
      </div>
    </div>
  );
}
