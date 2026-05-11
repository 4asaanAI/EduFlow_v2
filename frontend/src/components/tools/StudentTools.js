/**
 * All 10 Student Tools
 */
import React, { useState, useEffect } from 'react';
import { useUser } from '../../contexts/UserContext';
import { getAuthHeaders } from '../../lib/authSession';
import { ToolPage, StatCard, DataTable, Badge, ComingSoon, FormField, ActionBtn } from './ToolPage';
import { Brain, HelpCircle, Send } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';
function h() { return getAuthHeaders(); }

// 1. AI Tutor
export function AiTutor() {
  const { currentUser } = useUser();
  const [messages, setMessages] = useState([{ role: 'ai', text: `Hello ${currentUser.name}! I'm your AI tutor. I can help you understand concepts, solve doubts, and study smarter. What would you like to learn today?` }]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  const sendMessage = async () => {
    if (!input.trim() || loading) return;
    const userMsg = input.trim();
    setInput('');
    setMessages(prev => [...prev, { role: 'user', text: userMsg }]);
    setLoading(true);
    try {
      const res = await fetch(`${API}/chat/conversations/tutor/messages`, {
        method: 'POST',
        headers: h(currentUser),
        body: JSON.stringify({ text: userMsg }),
      });
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let aiText = '';
      setMessages(prev => [...prev, { role: 'ai', text: '' }]);
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        const events = chunk.split('\n\n').filter(e => e.startsWith('data: '));
        for (const event of events) {
          try {
            const data = JSON.parse(event.slice(6));
            if (data.type === 'text_delta') {
              aiText += data.delta;
              setMessages(prev => { const n = [...prev]; n[n.length - 1] = { role: 'ai', text: aiText }; return n; });
            }
          } catch {}
        }
      }
    } catch (err) {
      setMessages(prev => [...prev, { role: 'ai', text: 'Sorry, I had trouble connecting. Please try again.' }]);
    }
    setLoading(false);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: 'var(--c-app)' }}>
      <div style={{ padding: '16px 24px', borderBottom: '1px solid var(--c-border)', display: 'flex', alignItems: 'center', gap: 10 }}>
        <Brain size={18} color="#a78bfa" />
        <div>
          <h1 style={{ fontFamily: 'Inter, sans-serif', fontSize: 16, fontWeight: 600, color: 'var(--c-text)' }}>AI Tutor</h1>
          <p style={{ fontSize: 11, color: 'var(--c-faint)' }}>NCERT/CBSE curriculum • Assignment Helper</p>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
          <Badge text="CBSE" color="blue" />
        </div>
      </div>
      <div style={{ flex: 1, overflowY: 'auto', padding: '20px 24px' }}>
        {messages.map((msg, i) => (
          <div key={i} style={{ display: 'flex', justifyContent: msg.role === 'user' ? 'flex-end' : 'flex-start', marginBottom: 14 }}>
            {msg.role === 'ai' && (
              <div style={{ width: 28, height: 28, borderRadius: 7, background: 'rgba(139,92,246,0.2)', border: '1px solid rgba(139,92,246,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, marginRight: 10 }}>
                <Brain size={13} color="#a78bfa" />
              </div>
            )}
            <div style={{ maxWidth: '80%', background: msg.role === 'user' ? 'var(--c-input)' : 'transparent', border: msg.role === 'user' ? '1px solid var(--c-border)' : 'none', borderRadius: msg.role === 'user' ? '14px 14px 4px 14px' : 0, padding: msg.role === 'user' ? '10px 14px' : '0', color: 'var(--c-text)', fontSize: 13, lineHeight: 1.6 }}>
              {msg.text}
            </div>
          </div>
        ))}
        {loading && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ width: 28, height: 28, borderRadius: 7, background: 'rgba(139,92,246,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><Brain size={13} color="#a78bfa" /></div>
            <div style={{ display: 'flex', gap: 3 }}>
              <div className="typing-dot" /><div className="typing-dot" /><div className="typing-dot" />
            </div>
          </div>
        )}
      </div>
      <div style={{ padding: '12px 24px', borderTop: '1px solid var(--c-border)' }}>
        <div style={{ display: 'flex', gap: 8, background: 'var(--c-input)', border: '1px solid var(--c-border)', borderRadius: 12, padding: '8px 12px' }}>
          <input value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); } }} placeholder="Ask me anything about your syllabus..." disabled={loading} style={{ flex: 1, background: 'transparent', border: 'none', outline: 'none', color: 'var(--c-text)', fontSize: 13 }} />
          <button onClick={sendMessage} disabled={loading || !input.trim()} style={{ background: input.trim() ? '#a78bfa' : 'var(--c-border)', border: 'none', borderRadius: 8, padding: '6px 10px', cursor: 'pointer', display: 'flex', alignItems: 'center' }}>
            <Send size={13} color="#fff" />
          </button>
        </div>
        <p style={{ fontSize: 9, color: '#374151', textAlign: 'center', marginTop: 6 }}>AI tutor will guide with hints only for assignment questions. NCERT curriculum.</p>
      </div>
    </div>
  );
}

// 2. Doubt Solver
export function DoubtSolver() {
  const { currentUser } = useUser();
  const [doubt, setDoubt] = useState('');
  const [response, setResponse] = useState('');
  const [loading, setLoading] = useState(false);

  const solve = async () => {
    if (!doubt.trim() || loading) return;
    setLoading(true);
    setResponse('');
    try {
      const convId = `doubt-${Date.now()}`;
      const res = await fetch(`${API}/chat/conversations/${convId}/messages`, { method: 'POST', headers: h(currentUser), body: JSON.stringify({ text: `Doubt: ${doubt}` }) });
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let text = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        for (const line of chunk.split('\n\n')) {
          if (line.startsWith('data: ')) {
            try {
              const d = JSON.parse(line.slice(6));
              if (d.type === 'text_delta') { text += d.delta; setResponse(text); }
            } catch {}
          }
        }
      }
    } catch { setResponse('Could not solve doubt. Please try again.'); }
    setLoading(false);
  };

  return (
    <ToolPage title="Doubt Solver" subtitle="Get instant help with any concept">
      <div style={{ maxWidth: 600 }}>
        <div style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 11, padding: 20, marginBottom: 16 }}>
          <FormField label="Your Doubt or Question" type="textarea" value={doubt} onChange={setDoubt} placeholder="Type your doubt here... e.g. 'Explain photosynthesis with an example'" />
          <ActionBtn label={loading ? 'Solving...' : 'Solve My Doubt'} onClick={solve} disabled={loading} />
        </div>
        {response && (
          <div style={{ background: 'var(--c-bg)', border: '1px solid rgba(139,92,246,0.3)', borderRadius: 11, padding: 20 }}>
            <h3 style={{ fontFamily: 'Inter, sans-serif', color: '#a78bfa', fontSize: 13, fontWeight: 600, marginBottom: 10 }}>Answer</h3>
            <p style={{ color: 'var(--c-muted)', fontSize: 13, lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>{response}</p>
          </div>
        )}
      </div>
    </ToolPage>
  );
}

// 3. Homework & Assignment Viewer
export function HomeworkViewer() {
  const { currentUser } = useUser();
  const [assignments, setAssignments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedAssignment, setSelectedAssignment] = useState(null);
  useEffect(() => { fetch(`${API}/academics/assignments`, { headers: h(currentUser) }).then(r => r.json()).then(r => { if (r.success) setAssignments(r.data || []); }).finally(() => setLoading(false)); }, []);
  const today = new Date().toISOString().slice(0, 10);

  if (selectedAssignment) {
    const a = selectedAssignment;
    return (
      <ToolPage title={a.title} subtitle={a.subject_name} loading={false}>
        <div style={{ marginBottom: 16 }}>
          <button onClick={() => setSelectedAssignment(null)} style={{ background: 'none', border: 'none', color: '#4f8ff7', cursor: 'pointer', fontSize: 12, fontWeight: 600, padding: 0 }}>← Back to assignments</button>
        </div>
        <div style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 11, padding: 20, marginBottom: 16 }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12, marginBottom: 20 }}>
            <div>
              <p style={{ fontSize: 10, color: 'var(--c-faint)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>Subject</p>
              <p style={{ fontSize: 13, color: 'var(--c-text)', fontWeight: 500 }}>{a.subject_name || 'N/A'}</p>
            </div>
            <div>
              <p style={{ fontSize: 10, color: 'var(--c-faint)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>Due Date</p>
              <p style={{ fontSize: 13, color: 'var(--c-text)', fontWeight: 500 }}>{a.due_date ? new Date(a.due_date).toLocaleDateString() : 'No deadline'}</p>
            </div>
            <div>
              <p style={{ fontSize: 10, color: 'var(--c-faint)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 4 }}>Class</p>
              <p style={{ fontSize: 13, color: 'var(--c-text)', fontWeight: 500 }}>{a.class_name || 'N/A'}</p>
            </div>
          </div>
          {a.description && (
            <>
              <div style={{ borderTop: '1px solid var(--c-border)', paddingTop: 16, marginTop: 16 }}>
                <p style={{ fontSize: 10, color: 'var(--c-faint)', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>Instructions</p>
                <p style={{ fontSize: 13, color: 'var(--c-text)', lineHeight: 1.6, whiteSpace: 'pre-wrap', wordWrap: 'break-word' }}>{a.description}</p>
              </div>
            </>
          )}
        </div>
      </ToolPage>
    );
  }

  return (
    <ToolPage title="Homework & Assignments" subtitle="View your pending assignments" loading={loading}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10, marginBottom: 16, maxWidth: 500 }}>
        <StatCard value={assignments.length} label="TOTAL" color="#4f8ff7" />
        <StatCard value={assignments.filter(a => a.due_date && a.due_date < today).length} label="OVERDUE" color="#f87171" />
        <StatCard value={assignments.filter(a => !a.due_date || a.due_date >= today).length} label="UPCOMING" color="#34d399" />
      </div>
      <div style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 11, overflow: 'hidden' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--c-border)' }}>
              <th style={{ padding: '10px 14px', textAlign: 'left', fontSize: 10, fontWeight: 700, color: 'var(--c-faint)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Title</th>
              <th style={{ padding: '10px 14px', textAlign: 'left', fontSize: 10, fontWeight: 700, color: 'var(--c-faint)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Subject</th>
              <th style={{ padding: '10px 14px', textAlign: 'left', fontSize: 10, fontWeight: 700, color: 'var(--c-faint)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Due Date</th>
              <th style={{ padding: '10px 14px', textAlign: 'left', fontSize: 10, fontWeight: 700, color: 'var(--c-faint)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Status</th>
            </tr>
          </thead>
          <tbody>
            {assignments.length === 0 ? (
              <tr><td colSpan={4} style={{ padding: 20, textAlign: 'center', color: 'var(--c-faint)', fontSize: 12 }}>No assignments</td></tr>
            ) : (
              assignments.map((a, i) => {
                const isOverdue = a.due_date && a.due_date < today;
                return (
                  <tr key={i} onClick={() => setSelectedAssignment(a)} style={{ borderBottom: i < assignments.length - 1 ? '1px solid var(--c-border)' : 'none', cursor: 'pointer', background: 'transparent' }} onMouseEnter={e => e.currentTarget.style.background = 'rgba(99,102,241,0.04)'} onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                    <td style={{ padding: '10px 14px', fontSize: 12, color: 'var(--c-text)', fontWeight: 500 }}>{a.title}</td>
                    <td style={{ padding: '10px 14px', fontSize: 12, color: 'var(--c-muted)' }}>{a.subject_name || 'N/A'}</td>
                    <td style={{ padding: '10px 14px', fontSize: 12, color: 'var(--c-muted)' }}>{a.due_date ? new Date(a.due_date).toLocaleDateString() : 'No deadline'}</td>
                    <td style={{ padding: '10px 14px', fontSize: 12 }}><Badge text={isOverdue ? 'OVERDUE' : 'ACTIVE'} color={isOverdue ? 'red' : 'green'} /></td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
      <p style={{ fontSize: 11, color: 'var(--c-faint)', marginTop: 12, textAlign: 'center' }}>Click on any assignment to view full instructions</p>
    </ToolPage>
  );
}

// 4. Attendance Self-Check
export function AttendanceSelfCheck() {
  const { currentUser } = useUser();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => { import('../../lib/api').then(({ executeTool }) => executeTool('get_my_attendance', {}, currentUser).then(r => { if (r.success) setData(r.data); setLoading(false); })); }, []);
  return (
    <ToolPage title="My Attendance" subtitle="View your attendance record" loading={loading}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, marginBottom: 16, maxWidth: 600 }}>
        <StatCard value={data?.attendance_rate || '0%'} label="MY ATTENDANCE" color={parseFloat(data?.attendance_rate) >= 75 ? '#34d399' : '#f87171'} />
        <StatCard value={data?.present || 0} label="PRESENT DAYS" color="#34d399" />
        <StatCard value={data?.absent || 0} label="ABSENT DAYS" color="#f87171" />
        <StatCard value={data?.total_days || 0} label="TOTAL DAYS" color="var(--c-text)" />
      </div>
      {parseFloat(data?.attendance_rate) < 75 && (
        <div style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', borderRadius: 10, padding: '12px 16px', marginBottom: 16, fontSize: 12, color: '#fca5a5' }}>
          ⚠️ Your attendance is below 75%. You may not be eligible to appear in exams. Please contact your class teacher.
        </div>
      )}
      <DataTable title="Recent Records (Last 7 Days)" headers={['Date', 'Status']}
        rows={(data?.records || []).map(r => [r.date, <Badge text={r.status} color={{ present: 'green', absent: 'red', late: 'yellow' }[r.status] || 'gray'} />])}
        emptyMsg="No recent attendance records"
      />
    </ToolPage>
  );
}

// 5. Result Viewer
export function ResultViewer() {
  const { currentUser } = useUser();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => { import('../../lib/api').then(({ executeTool }) => executeTool('get_my_results', {}, currentUser).then(r => { if (r.success) setData(r.data); setLoading(false); })); }, []);
  return (
    <ToolPage title="My Results" subtitle="View your exam marks & grades" loading={loading}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10, marginBottom: 16, maxWidth: 400 }}>
        <StatCard value={data?.total_exams || 0} label="EXAMS" color="#4f8ff7" />
        <StatCard value={data?.student_name || currentUser.name} label="STUDENT" color="var(--c-text)" />
      </div>
      <DataTable headers={['Exam', 'Subject', 'Marks', 'Grade']}
        rows={(data?.results || []).map(r => [r.exam, r.subject, r.marks, <Badge text={r.grade} color={r.grade?.startsWith('A') ? 'green' : r.grade?.startsWith('B') ? 'blue' : 'yellow'} />])}
        emptyMsg="No results available yet"
      />
    </ToolPage>
  );
}

// 6. Practice Test Generator
export function PracticeTest() {
  const { currentUser } = useUser();
  const [subjects, setSubjects] = useState([
    { name: 'Mathematics' },
    { name: 'Science' },
    { name: 'English' },
    { name: 'Social Science' },
    { name: 'Hindi' }
  ]);
  const [selectedSubject, setSelectedSubject] = useState('');

  // ✅ NEW: Topic state
  const [topic, setTopic] = useState('');

  const [difficulty, setDifficulty] = useState('medium');
  const [questions, setQuestions] = useState([]);
  const [answers, setAnswers] = useState({});
  const [score, setScore] = useState(null);
  const [generating, setGenerating] = useState(false);

  const generateTest = async () => {
    if (!selectedSubject) return;
    setGenerating(true);
    setScore(null);
    setAnswers({});

    try {
      const convId = `practice-${Date.now()}`;

      // ✅ UPDATED PROMPT (topic added safely)
      const prompt = `Generate 5 multiple-choice questions for a CBSE student on subject: ${selectedSubject}${topic ? `, topic: ${topic}` : ''}. Difficulty: ${difficulty}. Format each question as:
Q: [question text]
A) [option A]
B) [option B]  
C) [option C]
D) [option D]
Answer: [correct letter]

Generate exactly 5 questions in this format.`;

      const res = await fetch(`${API}/chat/conversations/${convId}/messages`, {
        method: 'POST',
        headers: h(currentUser),
        body: JSON.stringify({ text: prompt }),
      });

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let fullText = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });

        for (const line of chunk.split('\n\n')) {
          if (line.startsWith('data: ')) {
            try {
              const d = JSON.parse(line.slice(6));
              if (d.type === 'text_delta') fullText += d.delta;
            } catch {}
          }
        }
      }

      const qBlocks = fullText.split(/Q:/).filter(b => b.trim());

      const parsed = qBlocks.slice(0, 5).map((block, i) => {
        const lines = block.trim().split('\n').filter(l => l.trim());
        const questionText = lines[0]?.trim() || `Question ${i + 1}`;
        const options = {};
        let correct = 'A';

        lines.forEach(l => {
          if (l.match(/^A\)/)) options.A = l.slice(2).trim();
          else if (l.match(/^B\)/)) options.B = l.slice(2).trim();
          else if (l.match(/^C\)/)) options.C = l.slice(2).trim();
          else if (l.match(/^D\)/)) options.D = l.slice(2).trim();
          else if (l.startsWith('Answer:')) {
            correct = l.replace('Answer:', '').trim()[0] || 'A';
          }
        });

        return { id: i, question: questionText, options, correct };
      });

      setQuestions(parsed.filter(q => Object.keys(q.options).length >= 2));
    } catch {
      setQuestions([]);
    }

    setGenerating(false);
  };

  const submitTest = () => {
    let correct = 0;
    questions.forEach(q => {
      if (answers[q.id] === q.correct) correct++;
    });

    setScore({
      correct,
      total: questions.length,
      pct: Math.round((correct / questions.length) * 100)
    });
  };

  return (
    <ToolPage title="Practice Test" subtitle="Self-assessment quizzes">
      <div style={{ display: 'flex', gap: 10, marginBottom: 16, flexWrap: 'wrap' }}>

        {/* Subject */}
        <select
          value={selectedSubject}
          onChange={e => setSelectedSubject(e.target.value)}
          style={{
            background: 'var(--c-bg)',
            border: '1px solid var(--c-border)',
            borderRadius: 7,
            padding: '8px 12px',
            color: 'var(--c-text)',
            fontSize: 12,
            outline: 'none'
          }}
        >
          <option value="">Select subject...</option>
          {subjects.map(s => (
            <option key={s.name} value={s.name}>{s.name}</option>
          ))}
        </select>

        {/* ✅ NEW: Topic Input */}
        <input
          type="text"
          placeholder="Enter topic"
          value={topic}
          onChange={e => setTopic(e.target.value)}
          style={{
            background: 'var(--c-bg)',
            border: '1px solid var(--c-border)',
            borderRadius: 7,
            padding: '8px 12px',
            color: 'var(--c-text)',
            fontSize: 12,
            outline: 'none'
          }}
        />

        {/* Difficulty */}
        <select
          value={difficulty}
          onChange={e => setDifficulty(e.target.value)}
          style={{
            background: 'var(--c-bg)',
            border: '1px solid var(--c-border)',
            borderRadius: 7,
            padding: '8px 12px',
            color: 'var(--c-text)',
            fontSize: 12,
            outline: 'none'
          }}
        >
          <option value="easy">Easy</option>
          <option value="medium">Medium</option>
          <option value="hard">Hard</option>
        </select>

        <ActionBtn
          label={generating ? 'Generating...' : 'Generate Test'}
          onClick={generateTest}
          disabled={generating || !selectedSubject}
        />
      </div>

      {score && (
        <div style={{
          background: score.pct >= 80 ? 'rgba(16,185,129,0.1)' : 'rgba(245,158,11,0.1)',
          border: `1px solid ${score.pct >= 80 ? 'rgba(16,185,129,0.3)' : 'rgba(245,158,11,0.3)'}`,
          borderRadius: 10,
          padding: '16px 20px',
          marginBottom: 16
        }}>
          <div style={{
            fontFamily: 'Inter, sans-serif',
            fontSize: 24,
            fontWeight: 700,
            color: score.pct >= 80 ? '#34d399' : '#fbbf24'
          }}>
            {score.correct}/{score.total}
          </div>
          <div style={{ fontSize: 13, color: 'var(--c-muted)' }}>
            {score.pct}% correct · {score.pct >= 80 ? 'Excellent!' : score.pct >= 60 ? 'Good effort!' : 'Keep practicing!'}
          </div>
        </div>
      )}

      {questions.map((q, qi) => (
        <div key={q.id} style={{
          background: score
            ? (answers[q.id] === q.correct ? 'rgba(16,185,129,0.05)' : 'rgba(239,68,68,0.05)')
            : 'var(--c-bg)',
          border: `1px solid ${
            score
              ? (answers[q.id] === q.correct ? 'rgba(16,185,129,0.2)' : 'rgba(239,68,68,0.2)')
              : 'var(--c-border)'
          }`,
          borderRadius: 10,
          padding: 16,
          marginBottom: 10
        }}>
          <p style={{ fontWeight: 600, color: 'var(--c-text)', fontSize: 13, marginBottom: 10 }}>
            {qi + 1}. {q.question}
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {Object.entries(q.options).map(([k, v]) => (
              <label key={k} style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                cursor: score ? 'default' : 'pointer',
                padding: '6px 10px',
                borderRadius: 7,
                background: (score && k === q.correct) ? 'rgba(16,185,129,0.15)' : 'transparent',
                border: `1px solid ${(score && k === q.correct) ? 'rgba(16,185,129,0.3)' : 'transparent'}`
              }}>
                <input
                  type="radio"
                  name={`q${q.id}`}
                  value={k}
                  checked={answers[q.id] === k}
                  onChange={() => !score && setAnswers(p => ({ ...p, [q.id]: k }))}
                  disabled={!!score}
                />
                <span style={{
                  fontSize: 12,
                  color: score && k === q.correct ? '#34d399' : 'var(--c-muted)'
                }}>
                  {k}) {v}
                </span>
              </label>
            ))}
          </div>
        </div>
      ))}

      {questions.length > 0 && !score && (
        <ActionBtn label="Submit Test" onClick={submitTest} />
      )}
    </ToolPage>
  );
}

// 7. Study Planner - FIXED (saves to DB)
export function StudyPlanner() {
  const { currentUser } = useUser();
  const [plan, setPlan] = useState({ monday: '', tuesday: '', wednesday: '', thursday: '', friday: '', saturday: '' });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const f = k => v => setPlan(p => ({ ...p, [k]: v }));

  useEffect(() => {
    fetch(`${API}/ops/study-plan`, { headers: h(currentUser) }).then(r => r.json())
      .then(r => { if (r.success && r.data) setPlan(r.data); })
      .catch(() => {}).finally(() => setLoading(false));
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      const r = await fetch(`${API}/ops/study-plan`, { method: 'POST', headers: h(currentUser), body: JSON.stringify(plan) }).then(r => r.json());
      if (r.success) { setSaved(true); setTimeout(() => setSaved(false), 3000); }
    } catch {}
    setSaving(false);
  };

  if (loading) return <ToolPage title="Study Planner" subtitle="Plan your week"><div style={{ color: 'var(--c-faint)', fontSize: 13 }}>Loading...</div></ToolPage>;

  return (
    <ToolPage title="Study Planner" subtitle="Plan your weekly study schedule">
      <div style={{ maxWidth: 600 }}>
        <p style={{ color: 'var(--c-faint)', fontSize: 12, marginBottom: 16 }}>Set your study goals for each day of the week. Your plan is saved automatically.</p>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 16 }}>
          {Object.keys(plan).filter(k => k !== 'user_id' && k !== 'updated_at').map(day => (
            <FormField key={day} label={day.charAt(0).toUpperCase() + day.slice(1)} value={plan[day] || ''} onChange={f(day)}
              placeholder={`e.g. Maths Chapter 5, Physics revision`} type="textarea" />
          ))}
        </div>
        <ActionBtn label={saved ? '✓ Saved!' : saving ? 'Saving...' : 'Save My Plan'} onClick={handleSave} disabled={saving} />
      </div>
    </ToolPage>
  );
}

// 8. Career Guidance AI - powered by LLM with student context
export function CareerGuidance() {
  const { currentUser } = useUser();
  const [input, setInput] = useState('');
  const [response, setResponse] = useState('');
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState(null);

  useEffect(() => {
    // Load student's results for context
    fetch(`${API}/academics/results`, { headers: h(currentUser) }).then(r => r.json())
      .then(r => { if (r.success) setResults(r.data || []); }).catch(() => {});
  }, []);

  const ask = async () => {
    if (!input.trim() || loading) return;
    setLoading(true);
    setResponse('');
    try {
      const context = results?.length > 0 ? `Student's results: ${results.map(r => `${r.subject_name}: ${r.marks_obtained}/${r.max_marks}`).join(', ')}.` : '';
      const prompt = `${context} Student asks: ${input}. Provide thoughtful career guidance for a CBSE school student in India, considering their academic performance and interests. Suggest specific career paths, required subjects, and entrance exams.`;
      const convId = `career-${Date.now()}`;
      const res = await fetch(`${API}/chat/conversations/${convId}/messages`, { method: 'POST', headers: h(currentUser), body: JSON.stringify({ text: prompt }) });
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let text = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        for (const line of chunk.split('\n\n')) {
          if (line.startsWith('data: ')) {
            try { const d = JSON.parse(line.slice(6)); if (d.type === 'text_delta') { text += d.delta; setResponse(text); } } catch {}
          }
        }
      }
    } catch { setResponse('Could not load guidance. Please try again.'); }
    setLoading(false);
  };

  const suggestions = ['What career should I choose based on my marks?', 'How to prepare for IIT JEE?', 'What are options after 10th?', 'Tell me about medical careers', 'What subjects for IAS/UPSC?'];

  return (
    <ToolPage title="Career Guidance AI" subtitle="AI-powered career advice based on your performance">
      <div style={{ maxWidth: 640 }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 7, marginBottom: 16 }}>
          {suggestions.map((s, i) => (
            <button key={i} onClick={() => setInput(s)} style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 7, padding: '6px 12px', color: 'var(--c-muted)', fontSize: 11, cursor: 'pointer' }}>{s}</button>
          ))}
        </div>
        <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
          <input value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === 'Enter' && ask()} placeholder="Ask about your career options..." disabled={loading}
            style={{ flex: 1, background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 8, padding: '10px 14px', color: 'var(--c-text)', fontSize: 13, outline: 'none' }} />
          <ActionBtn label={loading ? '...' : 'Ask'} onClick={ask} disabled={loading || !input.trim()} />
        </div>
        {response && (
          <div style={{ background: 'var(--c-bg)', border: '1px solid rgba(139,92,246,0.3)', borderRadius: 11, padding: 20 }}>
            <p style={{ color: 'var(--c-muted)', fontSize: 13, lineHeight: 1.7, whiteSpace: 'pre-wrap' }}>{response}</p>
          </div>
        )}
      </div>
    </ToolPage>
  );
}

// 9. Fee Status Viewer
export function FeeStatusViewer() {
  const { currentUser } = useUser();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => { import('../../lib/api').then(({ executeTool }) => executeTool('get_my_fees', {}, currentUser).then(r => { if (r.success) setData(r.data); setLoading(false); })); }, []);
  return (
    <ToolPage title="My Fee Status" subtitle="View your payment history" loading={loading}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 10, marginBottom: 16, maxWidth: 400 }}>
        <StatCard value={data?.total_paid || '₹0'} label="TOTAL PAID" color="#34d399" />
        <StatCard value={data?.total_pending || '₹0'} label="PENDING" color="#f87171" />
      </div>
      <DataTable headers={['Fee Type', 'Amount', 'Due Date', 'Status']}
        rows={(data?.transactions || []).map(t => [t.fee_type, t.amount, t.due_date || 'N/A', <Badge text={t.status} color={{ paid: 'green', pending: 'yellow', overdue: 'red' }[t.status] || 'gray'} />])}
        emptyMsg="No fee records"
      />
    </ToolPage>
  );
}

// 10. PTM Summary Viewer
export function PtmSummaryViewer() {
  const { currentUser } = useUser();
  const [notes, setNotes] = useState([]);
  const [loading, setLoading] = useState(true);
  useEffect(() => { fetch(`${API}/academics/ptm-notes`, { headers: h(currentUser) }).then(r => r.json()).then(r => { if (r.success) setNotes(r.data || []); }).finally(() => setLoading(false)); }, []);
  return (
    <ToolPage title="PTM Summary" subtitle="Read teacher notes from parent-teacher meetings" loading={loading}>
      {notes.length === 0 ? (
        <div style={{ padding: 32, textAlign: 'center', color: 'var(--c-faint)', background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 11, fontSize: 12 }}>No PTM notes recorded yet</div>
      ) : (
        notes.map((n, i) => (
          <div key={i} style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 10, padding: 16, marginBottom: 10 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
              <span style={{ fontWeight: 600, color: 'var(--c-text)', fontSize: 13 }}>PTM Notes</span>
              <span style={{ fontSize: 11, color: 'var(--c-faint)' }}>{n.created_at?.slice(0, 10)}</span>
            </div>
            <p style={{ fontSize: 13, color: 'var(--c-muted)', lineHeight: 1.6 }}>{n.notes}</p>
          </div>
        ))
      )}
    </ToolPage>
  );
}

// 11. Form Submissions
export function FormSubmissions() {
  const { currentUser } = useUser();
  const [forms, setForms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedForm, setSelectedForm] = useState(null);
  const [answers, setAnswers] = useState({});
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState('');

  const load = async () => {
    setLoading(true);
    try {
      const r = await fetch(`${API}/settings/forms`, { headers: h(currentUser) }).then(r => r.json());
      if (r.success) {
        const availableForms = r.data?.filter(f => {
          if (f.audience === 'all') return true;
          if (f.audience === 'students' && currentUser.role === 'student') return true;
          if (f.audience === 'teachers' && currentUser.role === 'teacher') return true;
          if (f.audience === 'parents') return true;
          return false;
        }) || [];
        setForms(availableForms);
      }
    } catch {}
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  const handleSelectForm = (form) => {
    setSelectedForm(form);
    setAnswers({});
    setSubmitted(false);
    setError('');
  };

  const handleAnswerChange = (fieldLabel, value) => {
    setAnswers(p => ({ ...p, [fieldLabel]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    const requiredFields = selectedForm.fields.filter(f => !f.optional);
    const unanswered = requiredFields.find(f => !answers[f.label]);
    if (unanswered) {
      setError(`${unanswered.label} is required`);
      return;
    }
    try {
      const res = await fetch(`${API}/settings/forms/${selectedForm.id}/responses`, {
        method: 'POST',
        headers: h(currentUser),
        body: JSON.stringify({ answers })
      }).then(r => r.json());
      if (res.success) {
        setSubmitted(true);
        setTimeout(() => {
          setSelectedForm(null);
          setAnswers({});
          setSubmitted(false);
        }, 2000);
      } else {
        setError(res.detail || 'Failed to submit form');
      }
    } catch {
      setError('Network error');
    }
  };

  return (
    <ToolPage title="Forms" subtitle="Complete requested surveys and forms" loading={loading}>
      {!selectedForm ? (
        forms.length === 0 ? (
          <div style={{ textAlign: 'center', color: 'var(--c-faint)', padding: '60px 20px' }}>
            <p>No forms available at the moment</p>
          </div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 12 }}>
            {forms.map(form => (
              <div key={form.id} onClick={() => handleSelectForm(form)} style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 11, padding: 16, cursor: 'pointer', transition: 'all 0.2s', transform: 'scale(1)' }} onMouseOver={e => e.currentTarget.style.transform = 'scale(1.02)'} onMouseOut={e => e.currentTarget.style.transform = 'scale(1)'}>
                <h4 style={{ color: 'var(--c-text)', fontSize: 13, fontWeight: 600, marginBottom: 8 }}>{form.title}</h4>
                <p style={{ color: 'var(--c-faint)', fontSize: 11, marginBottom: 10 }}>{form.fields?.length || 0} fields</p>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: 10, color: 'var(--c-muted)', textTransform: 'capitalize' }}>{form.audience}</span>
                  <span style={{ color: '#4f8ff7', fontSize: 11, fontWeight: 500 }}>Fill →</span>
                </div>
              </div>
            ))}
          </div>
        )
      ) : (
        <>
          <div style={{ marginBottom: 14 }}>
            <button onClick={() => { setSelectedForm(null); setSubmitted(false); }} style={{ padding: '6px 12px', borderRadius: 6, border: '1px solid var(--c-border)', background: 'var(--c-bg)', color: 'var(--c-muted)', fontSize: 12, cursor: 'pointer' }}>← Back</button>
          </div>
          {submitted ? (
            <div style={{ textAlign: 'center', padding: '60px 20px' }}>
              <div style={{ fontSize: 36, marginBottom: 12 }}>✓</div>
              <p style={{ color: '#34d399', fontSize: 14, fontWeight: 500, marginBottom: 8 }}>Form Submitted Successfully!</p>
              <p style={{ color: 'var(--c-faint)', fontSize: 12 }}>Your response has been recorded.</p>
            </div>
          ) : (
            <form onSubmit={handleSubmit}>
              <div style={{ background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 11, padding: 20, marginBottom: 16 }}>
                <h3 style={{ fontFamily: 'Inter, sans-serif', color: 'var(--c-text)', fontSize: 14, fontWeight: 600, marginBottom: 16 }}>{selectedForm.title}</h3>
                {selectedForm.fields?.map((field, i) => (
                  <div key={i} style={{ marginBottom: 16 }}>
                    <label style={{ fontSize: 12, color: '#d4d4d4', fontWeight: 500, display: 'block', marginBottom: 6 }}>
                      {field.label}
                    </label>
                    {field.type === 'text' && (
                      <input type="text" value={answers[field.label] || ''} onChange={e => handleAnswerChange(field.label, e.target.value)} style={{ width: '100%', background: 'var(--c-deep)', border: '1px solid var(--c-border)', borderRadius: 6, padding: '8px 10px', color: 'var(--c-text)', fontSize: 12, outline: 'none', boxSizing: 'border-box' }} required />
                    )}
                    {field.type === 'number' && (
                      <input type="number" value={answers[field.label] || ''} onChange={e => handleAnswerChange(field.label, e.target.value)} style={{ width: '100%', background: 'var(--c-deep)', border: '1px solid var(--c-border)', borderRadius: 6, padding: '8px 10px', color: 'var(--c-text)', fontSize: 12, outline: 'none', boxSizing: 'border-box' }} required />
                    )}
                    {field.type === 'email' && (
                      <input type="email" value={answers[field.label] || ''} onChange={e => handleAnswerChange(field.label, e.target.value)} style={{ width: '100%', background: 'var(--c-deep)', border: '1px solid var(--c-border)', borderRadius: 6, padding: '8px 10px', color: 'var(--c-text)', fontSize: 12, outline: 'none', boxSizing: 'border-box' }} required />
                    )}
                    {field.type === 'date' && (
                      <input type="date" value={answers[field.label] || ''} onChange={e => handleAnswerChange(field.label, e.target.value)} style={{ width: '100%', background: 'var(--c-deep)', border: '1px solid var(--c-border)', borderRadius: 6, padding: '8px 10px', color: 'var(--c-text)', fontSize: 12, outline: 'none', boxSizing: 'border-box' }} required />
                    )}
                    {field.type === 'textarea' && (
                      <textarea value={answers[field.label] || ''} onChange={e => handleAnswerChange(field.label, e.target.value)} placeholder="Type your answer here..." style={{ width: '100%', background: 'var(--c-deep)', border: '1px solid var(--c-border)', borderRadius: 6, padding: '8px 10px', color: 'var(--c-text)', fontSize: 12, outline: 'none', boxSizing: 'border-box', minHeight: '80px', fontFamily: 'inherit' }} required />
                    )}
                    {(field.type === 'select') && (
                      <select value={answers[field.label] || ''} onChange={e => handleAnswerChange(field.label, e.target.value)} style={{ width: '100%', background: 'var(--c-deep)', border: '1px solid var(--c-border)', borderRadius: 6, padding: '8px 10px', color: 'var(--c-text)', fontSize: 12, outline: 'none', boxSizing: 'border-box' }} required>
                        <option value="">Select an option</option>
                        {field.options?.map(opt => <option key={opt} value={opt}>{opt}</option>)}
                      </select>
                    )}
                    {field.type === 'radio' && (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                        {field.options?.map(opt => (
                          <label key={opt} style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', color: 'var(--c-text)', fontSize: 12 }}>
                            <input type="radio" name={field.label} value={opt} checked={answers[field.label] === opt} onChange={e => handleAnswerChange(field.label, e.target.value)} style={{ cursor: 'pointer' }} required />
                            {opt}
                          </label>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
                {error && <div style={{ color: '#f87171', fontSize: 12, marginBottom: 12 }}>{error}</div>}
                <div style={{ display: 'flex', gap: 8 }}>
                  <ActionBtn label="Submit Form" type="submit" icon={<Send size={11} />} />
                  <ActionBtn label="Cancel" variant="secondary" onClick={() => { setSelectedForm(null); setAnswers({}); }} />
                </div>
              </div>
            </form>
          )}
        </>
      )}
    </ToolPage>
  );
}
