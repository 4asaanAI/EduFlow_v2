import React, { useCallback, useEffect, useState } from 'react';
import { API, apiFetch } from '../../lib/api';
import { getAuthHeaders } from '../../lib/authSession';
import { ActionBtn, Badge, DataTable, FormField, ToolPage } from './ToolPage';

async function request(url, options = {}) {
  const response = await apiFetch(url, {
    ...options,
    headers: { ...getAuthHeaders(), ...(options.body ? { 'Content-Type': 'application/json' } : {}) },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || 'Quiz operation failed');
  return body;
}

export function PracticeTest() {
  const [quizzes, setQuizzes] = useState([]);
  const [attempt, setAttempt] = useState(null);
  const [answers, setAnswers] = useState({});
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const load = useCallback(async () => {
    setLoading(true);
    try { const body = await request(`${API}/quizzes`); setQuizzes(body.data || []); }
    catch (err) { setError(err.message); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);
  async function start(id) {
    try { const body = await request(`${API}/quizzes/${id}/attempts`, { method: 'POST' }); setAttempt(body.data); setAnswers({}); setResult(null); }
    catch (err) { setError(err.message); }
  }
  async function submit() {
    try { const body = await request(`${API}/quizzes/attempts/${attempt.id}/submit`, { method: 'POST', body: JSON.stringify({ answers }) }); setResult(body.data); }
    catch (err) { setError(err.message); }
  }
  return <ToolPage title="Practice Tests" subtitle="Published school quizzes with secure server-side grading" loading={loading} onRefresh={load}>
    {error && <ErrorText text={error} />}
    {!attempt && <DataTable headers={['Quiz', 'Questions', 'Points', 'Duration', 'Action']}
      rows={quizzes.map(item => [item.title, item.question_count, item.total_points, `${item.duration_minutes} min`, <ActionBtn label="Start" onClick={() => start(item.id)} />])} emptyMsg="No published quizzes for your class" />}
    {attempt?.quiz && <div>
      <h3 style={{ color: 'var(--c-text)', fontSize: 16 }}>{attempt.quiz.title}</h3>
      {attempt.quiz.questions.map((question, index) => <section key={question.id} style={questionPanel}>
        <p style={{ color: 'var(--c-text)', fontWeight: 650 }}>{index + 1}. {question.prompt}</p>
        {question.options.map((option, optionIndex) => <label key={optionIndex} style={optionRow}>
          <input type="radio" name={question.id} checked={Number(answers[question.id]) === optionIndex} disabled={!!result} onChange={() => setAnswers(value => ({ ...value, [question.id]: optionIndex }))} />
          <span>{option}</span>
        </label>)}
        {result && result.result_detail?.find(item => item.question_id === question.id) && <div style={{ color: result.result_detail.find(item => item.question_id === question.id).correct ? 'var(--tool-hex-34d399)' : 'var(--tool-hex-f87171)', fontSize: 11, marginTop: 8 }}>{result.result_detail.find(item => item.question_id === question.id).correct ? 'Correct' : 'Review this answer'}</div>}
      </section>)}
      {!result ? <ActionBtn label="Submit quiz" onClick={submit} /> : <div style={scorePanel}><strong>{result.score}/{result.total_points}</strong><span>{result.percentage}%</span><ActionBtn label="Back to quizzes" variant="secondary" onClick={() => setAttempt(null)} /></div>}
    </div>}
  </ToolPage>;
}

const blankQuestion = () => ({ prompt: '', options: ['', '', '', ''], correct_option: 0, points: 1 });

export function QuizManager() {
  const [quizzes, setQuizzes] = useState([]);
  const [classes, setClasses] = useState([]);
  const [form, setForm] = useState({ title: '', class_id: '', duration_minutes: 30, max_attempts: 1, questions: [blankQuestion()] });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [quizBody, classBody] = await Promise.all([request(`${API}/quizzes`), request(`${API}/settings/classes`)]);
      setQuizzes(quizBody.data || []); setClasses(classBody.data || []);
      setForm(value => ({ ...value, class_id: value.class_id || classBody.data?.[0]?.id || '' }));
    } catch (err) { setError(err.message); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);
  function updateQuestion(index, field, value) {
    setForm(current => ({ ...current, questions: current.questions.map((question, questionIndex) => questionIndex === index ? { ...question, [field]: value } : question) }));
  }
  function updateOption(questionIndex, optionIndex, value) {
    setForm(current => ({ ...current, questions: current.questions.map((question, index) => index === questionIndex ? { ...question, options: question.options.map((option, currentOption) => currentOption === optionIndex ? value : option) } : question) }));
  }
  async function create(event) {
    event.preventDefault();
    try { await request(`${API}/quizzes`, { method: 'POST', body: JSON.stringify(form) }); setForm(value => ({ ...value, title: '', questions: [blankQuestion()] })); await load(); }
    catch (err) { setError(err.message); }
  }
  async function publish(id) {
    try { await request(`${API}/quizzes/${id}/publish`, { method: 'PATCH' }); await load(); }
    catch (err) { setError(err.message); }
  }
  return <ToolPage title="Quiz Manager" subtitle="Author, publish, and review server-graded school quizzes" loading={loading} onRefresh={load}>
    {error && <ErrorText text={error} />}
    <form onSubmit={create} style={formPanel}>
      <div className="responsive-form-grid" style={formGrid}>
        <FormField label="Quiz title" value={form.title} onChange={value => setForm(item => ({ ...item, title: value }))} required />
        <FormField label="Class" type="select" value={form.class_id} onChange={value => setForm(item => ({ ...item, class_id: value }))} options={classes.map(item => ({ value: item.id, label: `${item.name}${item.section ? ` - ${item.section}` : ''}` }))} />
        <FormField label="Duration minutes" type="number" value={form.duration_minutes} onChange={value => setForm(item => ({ ...item, duration_minutes: Number(value) }))} />
        <FormField label="Maximum attempts" type="number" value={form.max_attempts} onChange={value => setForm(item => ({ ...item, max_attempts: Number(value) }))} />
      </div>
      {form.questions.map((question, questionIndex) => <div key={questionIndex} style={questionPanel}>
        <FormField label={`Question ${questionIndex + 1}`} value={question.prompt} onChange={value => updateQuestion(questionIndex, 'prompt', value)} required />
        <div className="responsive-form-grid" style={formGrid}>{question.options.map((option, optionIndex) => <FormField key={optionIndex} label={`Option ${optionIndex + 1}`} value={option} onChange={value => updateOption(questionIndex, optionIndex, value)} required />)}</div>
        <div style={formGrid}><FormField label="Correct option" type="select" value={question.correct_option} onChange={value => updateQuestion(questionIndex, 'correct_option', Number(value))} options={question.options.map((_, optionIndex) => ({ value: optionIndex, label: `Option ${optionIndex + 1}` }))} /><FormField label="Points" type="number" value={question.points} onChange={value => updateQuestion(questionIndex, 'points', Number(value))} /></div>
      </div>)}
      <div style={{ display: 'flex', gap: 7, flexWrap: 'wrap' }}><ActionBtn label="Add question" variant="secondary" onClick={() => setForm(item => ({ ...item, questions: [...item.questions, blankQuestion()] }))} /><ActionBtn label="Save draft" type="submit" /></div>
    </form>
    <DataTable headers={['Quiz', 'Class', 'Questions', 'Status', 'Action']}
      rows={quizzes.map(item => [item.title, classes.find(row => row.id === item.class_id)?.name || item.class_id, item.question_count, <Badge text={item.status} color={item.status === 'published' ? 'green' : 'yellow'} />, item.status === 'draft' ? <ActionBtn label="Publish" onClick={() => publish(item.id)} /> : 'Published'])} emptyMsg="No quizzes authored" />
  </ToolPage>;
}

function ErrorText({ text }) { return <div role="alert" style={{ color: 'var(--tool-hex-f87171)', fontSize: 12, marginBottom: 12 }}>{text}</div>; }
const formPanel = { background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 10, padding: 14, marginBottom: 16 };
const formGrid = { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(170px, 100%), 1fr))', gap: 9 };
const questionPanel = { background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 10, padding: 14, marginBottom: 10 };
const optionRow = { display: 'flex', gap: 8, alignItems: 'center', padding: '7px 9px', color: 'var(--c-muted)', fontSize: 12 };
const scorePanel = { display: 'flex', alignItems: 'center', gap: 12, color: 'var(--tool-hex-34d399)', background: 'color-mix(in srgb, var(--tool-hex-34d399) 8%, transparent)', borderRadius: 9, padding: 14 };
