import { staffGateway } from '../../app/staffGateway'

const DB_NAME = 'weave-cbt-ai-question-drafts'
const DB_VERSION = 1
const STORE_NAME = 'drafts'

function openDraftDatabase(indexedDBImpl = globalThis.indexedDB) {
  if (!indexedDBImpl) throw new Error('IndexedDB is unavailable in this browser.')
  return new Promise((resolve, reject) => {
    const request = indexedDBImpl.open(DB_NAME, DB_VERSION)
    request.onupgradeneeded = () => {
      const database = request.result
      if (!database.objectStoreNames.contains(STORE_NAME)) {
        database.createObjectStore(STORE_NAME, { keyPath: 'draft_id' })
      }
    }
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error || new Error('Unable to open AI draft storage.'))
  })
}

function transact(database, mode, action) {
  return new Promise((resolve, reject) => {
    const transaction = database.transaction(STORE_NAME, mode)
    const store = transaction.objectStore(STORE_NAME)
    let request
    try {
      request = action(store)
    } catch (error) {
      reject(error)
      return
    }
    if (request) {
      request.onsuccess = () => resolve(request.result)
      request.onerror = () => reject(request.error || new Error('AI draft storage operation failed.'))
    } else {
      transaction.oncomplete = () => resolve(undefined)
    }
    transaction.onerror = () => reject(transaction.error || new Error('AI draft storage transaction failed.'))
  })
}

export function createQuestionAIDraftStore({ indexedDBImpl = globalThis.indexedDB } = {}) {
  return {
    async put(draft) {
      const database = await openDraftDatabase(indexedDBImpl)
      try {
        await transact(database, 'readwrite', (store) => store.put(draft))
      } finally {
        database.close()
      }
      return draft
    },
    async get(draftId) {
      const database = await openDraftDatabase(indexedDBImpl)
      try {
        return await transact(database, 'readonly', (store) => store.get(draftId))
      } finally {
        database.close()
      }
    },
    async delete(draftId) {
      const database = await openDraftDatabase(indexedDBImpl)
      try {
        await transact(database, 'readwrite', (store) => store.delete(draftId))
      } finally {
        database.close()
      }
    },
  }
}

function defaultOperationId() {
  if (!globalThis.crypto?.randomUUID) {
    throw new Error('Secure browser UUID generation is unavailable.')
  }
  return globalThis.crypto.randomUUID()
}

export function createQuestionAIController({
  questionsApi = staffGateway.questions,
  draftStore = createQuestionAIDraftStore(),
  createOperationId = defaultOperationId,
} = {}) {
  async function generate(bankId, input, { operationId } = {}) {
    const operation_id = operationId || createOperationId()
    const response = await questionsApi.generateAIQuestionDrafts(bankId, {
      ...input,
      operation_id,
    })
    const draft = {
      draft_id: response.operation_id,
      bank_id: bankId,
      generation_operation_id: response.operation_id,
      questions: response.questions,
      repaired: response.repaired,
      generation_charge: response.charge,
      regeneration_charges: [],
      updated_at: new Date().toISOString(),
    }
    await draftStore.put(draft)
    return draft
  }

  async function regenerateDraft(
    draftId,
    questionIndex,
    input,
    { operationId } = {},
  ) {
    const draft = await draftStore.get(draftId)
    if (!draft) throw new Error('AI question draft was not found.')
    const existingQuestion = draft.questions?.[questionIndex]
    if (!existingQuestion) throw new Error('AI question draft item was not found.')

    const operation_id = operationId || createOperationId()
    const response = await questionsApi.regenerateAIQuestionDraft(draft.bank_id, {
      ...input,
      operation_id,
      existing_question: existingQuestion,
    })
    const questions = [...draft.questions]
    questions[questionIndex] = response.question
    const updated = {
      ...draft,
      questions,
      regeneration_charges: [
        ...(draft.regeneration_charges || []),
        { operation_id: response.operation_id, charge: response.charge },
      ],
      updated_at: new Date().toISOString(),
    }
    await draftStore.put(updated)
    return updated
  }

  async function regenerateStored(questionId, input, { operationId } = {}) {
    const operation_id = operationId || createOperationId()
    return questionsApi.regenerateStoredQuestionWithAI(questionId, {
      ...input,
      operation_id,
    })
  }

  async function save(draftId, questions = null) {
    const draft = await draftStore.get(draftId)
    if (!draft) throw new Error('AI question draft was not found.')
    const result = await questionsApi.saveAIQuestionDrafts(draft.bank_id, {
      draft_id: draft.draft_id,
      questions: questions || draft.questions,
    })
    // Keep the IndexedDB copy through every failure path. It is removed only
    // after the CBT backend confirms permanent local persistence.
    await draftStore.delete(draftId)
    return result
  }

  return {
    generate,
    retryGeneration: (bankId, input, operationId) => (
      generate(bankId, input, { operationId })
    ),
    regenerateDraft,
    retryDraftRegeneration: (draftId, questionIndex, input, operationId) => (
      regenerateDraft(draftId, questionIndex, input, { operationId })
    ),
    regenerateStored,
    getDraft: (draftId) => draftStore.get(draftId),
    discardDraft: (draftId) => draftStore.delete(draftId),
    save,
  }
}
