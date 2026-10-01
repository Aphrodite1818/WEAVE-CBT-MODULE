import { describe, expect, it, vi } from 'vitest'

import { createQuestionAIController } from './questionAIController'

function memoryDraftStore() {
  const rows = new Map()
  return {
    put: vi.fn(async (row) => {
      rows.set(row.draft_id, structuredClone(row))
      return row
    }),
    get: vi.fn(async (id) => rows.get(id)),
    delete: vi.fn(async (id) => rows.delete(id)),
    rows,
  }
}

function generatedResponse(operationId) {
  return {
    operation_id: operationId,
    questions: [
      {
        question_type: 'single_choice',
        prompt: 'Question?',
        instruction: null,
        image: null,
        options: [
          { text: 'A', image: null, is_correct: true },
          { text: 'B', image: null, is_correct: false },
        ],
      },
    ],
    repaired: false,
    charge: {
      reservation_id: '00000000-0000-0000-0000-000000000001',
      credits_charged: 1,
      credits_released: 0,
    },
  }
}

describe('question AI controller', () => {
  it('reuses the supplied operation id for an uncertain generation retry', async () => {
    const store = memoryDraftStore()
    const questionsApi = {
      generateAIQuestionDrafts: vi.fn(async (_bankId, payload) => generatedResponse(payload.operation_id)),
    }
    const controller = createQuestionAIController({
      questionsApi,
      draftStore: store,
      createOperationId: () => 'new-operation',
    })

    await controller.retryGeneration('bank-1', { generation_prompt: 'Cells', question_count: 1 }, 'same-operation')

    expect(questionsApi.generateAIQuestionDrafts).toHaveBeenCalledWith(
      'bank-1',
      expect.objectContaining({ operation_id: 'same-operation' }),
    )
    expect(store.rows.has('same-operation')).toBe(true)
  })

  it('keeps the IndexedDB draft when permanent save fails', async () => {
    const store = memoryDraftStore()
    await store.put({
      draft_id: 'draft-1',
      bank_id: 'bank-1',
      questions: generatedResponse('draft-1').questions,
    })
    const questionsApi = {
      saveAIQuestionDrafts: vi.fn(async () => {
        throw new Error('network lost')
      }),
    }
    const controller = createQuestionAIController({ questionsApi, draftStore: store })

    await expect(controller.save('draft-1')).rejects.toThrow('network lost')
    expect(store.rows.has('draft-1')).toBe(true)
  })

  it('clears the IndexedDB draft only after CBT confirms persistence', async () => {
    const store = memoryDraftStore()
    await store.put({
      draft_id: 'draft-1',
      bank_id: 'bank-1',
      questions: generatedResponse('draft-1').questions,
    })
    const questionsApi = {
      saveAIQuestionDrafts: vi.fn(async () => ({ draft_id: 'draft-1', questions: [] })),
    }
    const controller = createQuestionAIController({ questionsApi, draftStore: store })

    await controller.save('draft-1')
    expect(store.rows.has('draft-1')).toBe(false)
  })
})
