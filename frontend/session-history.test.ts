import assert from 'node:assert/strict'
import test from 'node:test'
import { persistentHistory, rememberTurn } from './src/sessionHistory.ts'

type Sample = { question: string; answer: string; privateDocument?: boolean }

const ordinary = (question: string): Sample => ({ question, answer: 'synthetic' })
const attached = (question: string): Sample => ({ ...ordinary(question), privateDocument: true })

test('attached turns stay in the session and out of stored history', () => {
  let history: Sample[] = []
  for (let index = 0; index < 30; index += 1) history = rememberTurn(history, ordinary(`ordinary-${index}`))
  history = rememberTurn(history, attached('session-only'))
  const stored = persistentHistory(history)
  assert.equal(stored.length, 30)
  assert.equal(stored[0].question, 'ordinary-0')
  assert.equal(stored.at(-1)?.question, 'ordinary-29')
  assert.equal(history.at(-1)?.privateDocument, true)
  const serialized = JSON.stringify(stored)
  assert.equal(serialized.includes('session-only'), false)
  assert.equal(serialized.includes('privateDocument'), false)
})

test('ordinary history keeps its limit without dropping a session-only turn', () => {
  let history = rememberTurn([] as Sample[], attached('session-only'))
  for (let index = 0; index < 31; index += 1) history = rememberTurn(history, ordinary(`ordinary-${index}`))
  const stored = persistentHistory(history)
  assert.equal(stored.length, 30)
  assert.equal(stored[0].question, 'ordinary-1')
  assert.equal(stored.some((turn) => turn.question === 'session-only'), false)
  assert.equal(history.some((turn) => turn.question === 'session-only'), true)
})

test('history stored before this change is left intact', () => {
  const legacy = [{ question: 'already-stored', answer: 'kept' }]
  assert.deepEqual(persistentHistory(legacy), legacy)
})

test('private capacity overflow keeps the ordinary set and stays out of stored JSON', () => {
  let history: Sample[] = []
  for (let index = 0; index < 30; index += 1) history = rememberTurn(history, ordinary(`ordinary-${index}`))
  const ordinaryItems = history.map((turn) => ({ question: turn.question, answer: turn.answer }))
  for (let index = 0; index < 31; index += 1) {
    history = rememberTurn(history, {
      question: `private-question-${index}`,
      answer: `private-answer-${index}`,
      privateDocument: true,
    })
  }
  const ordinaryAfter = history
    .filter((turn) => !turn.privateDocument)
    .map((turn) => ({ question: turn.question, answer: turn.answer }))
  assert.deepEqual(ordinaryAfter, ordinaryItems)
  assert.deepEqual(
    history.filter((turn) => turn.privateDocument).map((turn) => turn.question),
    Array.from({ length: 30 }, (_, index) => `private-question-${index + 1}`),
  )
  const serialized = JSON.stringify(persistentHistory(history))
  for (let index = 0; index < 31; index += 1) {
    assert.equal(serialized.includes(`private-question-${index}`), false)
    assert.equal(serialized.includes(`private-answer-${index}`), false)
  }
})
