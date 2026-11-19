export const HISTORY_LIMIT = 30
export const PRIVATE_HISTORY_LIMIT = 30

type SessionTurn = { privateDocument?: boolean; sessionOnly?: boolean }

export function rememberTurn<T extends SessionTurn>(
  history: readonly T[],
  turn: T,
  limit = HISTORY_LIMIT,
  privateLimit = PRIVATE_HISTORY_LIMIT,
): T[] {
  const next = history.concat(turn)
  const trimOrdinary = !(turn.privateDocument || turn.sessionOnly)
  let ordinaryKept = 0
  let privateKept = 0
  const selected: T[] = []
  for (let index = next.length - 1; index >= 0; index -= 1) {
    const item = next[index]
    if (item.privateDocument || item.sessionOnly) {
      if (privateKept < privateLimit) {
        selected.push(item)
        privateKept += 1
      }
    } else if (!trimOrdinary || ordinaryKept < limit) {
      selected.push(item)
      ordinaryKept += 1
    }
  }
  return selected.reverse()
}

export function persistentHistory<T extends SessionTurn>(
  history: readonly T[],
): Omit<T, 'privateDocument' | 'sessionOnly'>[] {
  return history.flatMap((turn) => {
    if (turn.privateDocument || turn.sessionOnly) return []
    const { privateDocument: _privateDocument, sessionOnly: _sessionOnly, ...stored } = turn
    return [stored]
  })
}
