import { useEffect, useMemo, useState } from 'react'
import { leafGateway } from '../../services/leafGateway'
import { TeacherLayout } from './TeacherLayout'
import { OverviewPage } from './OverviewPage'
import { BankDetailPage, QuestionBanksPage } from './QuestionBanksPage'
import { CreateQuestionPage, QuestionsPage } from './QuestionsPage'
import { CreateExamPage, ExamsPage } from './ExamsPage'

export function TeacherWorkspace({ state, dispatch, signOut, gateway = leafGateway }) {
  const teacherData = useTeacherData(gateway)

  return (
    <TeacherLayout state={state} dispatch={dispatch} signOut={signOut}>
      {state.staff.section === 'overview' && <OverviewPage state={state} dispatch={dispatch} teacherData={teacherData} />}
      {state.staff.section === 'question-banks' && <QuestionBanksPage state={state} dispatch={dispatch} teacherData={teacherData} />}
      {state.staff.section === 'bank-detail' && <BankDetailPage state={state} dispatch={dispatch} teacherData={teacherData} />}
      {state.staff.section === 'questions' && <QuestionsPage state={state} dispatch={dispatch} teacherData={teacherData} />}
      {state.staff.section === 'create-question' && <CreateQuestionPage state={state} dispatch={dispatch} teacherData={teacherData} gateway={gateway} />}
      {state.staff.section === 'exams' && <ExamsPage state={state} dispatch={dispatch} teacherData={teacherData} />}
      {state.staff.section === 'create-exam' && <CreateExamPage state={state} dispatch={dispatch} teacherData={teacherData} />}
    </TeacherLayout>
  )
}

function useTeacherData(gateway) {
  const [banks, setBanks] = useState([])
  const [questions, setQuestions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const refresh = useMemo(() => async () => {
    setLoading(true)
    setError('')
    try {
      const loaded = await loadTeacherData(gateway)
      setBanks(loaded.banks)
      setQuestions(loaded.questions)
    } catch (error) {
      setError(error.userMessage || 'Leaf could not load teacher content.')
      setBanks([])
      setQuestions([])
    } finally {
      setLoading(false)
    }
  }, [gateway])

  useEffect(() => {
    let cancelled = false
    loadTeacherData(gateway)
      .then((loaded) => {
        if (cancelled) return
        setBanks(loaded.banks)
        setQuestions(loaded.questions)
      })
      .catch((error) => {
        if (cancelled) return
        setError(error.userMessage || 'Leaf could not load teacher content.')
        setBanks([])
        setQuestions([])
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [gateway])

  return { banks, questions, loading, error, refresh }
}

async function loadTeacherData(gateway) {
  const bankRows = await gateway.questions.listAuthorableQuestionBanks()
  const questionGroups = await Promise.all(
    bankRows.map((bank) =>
      gateway.questions
        .listQuestionsForBank(bank.id)
        .then((items) => items.map((question) => normalizeQuestion(question, bank)))
        .catch(() => []),
    ),
  )
  const questions = questionGroups.flat()
  return {
    banks: bankRows.map((bank) => normalizeBank(bank, questions)),
    questions,
  }
}

function normalizeBank(bank, questions) {
  return {
    id: bank.id,
    curriculumSubjectId: bank.curriculum_subject_id,
    name: bank.name,
    description: bank.description,
    status: bank.is_active ? 'Ready' : 'Archived',
    count: questions.filter((question) => question.bankId === bank.id).length,
  }
}

function normalizeQuestion(question, bank) {
  return {
    id: question.id,
    bankId: question.bank_id,
    prompt: question.prompt,
    type: question.question_type === 'multiple_choice' ? 'Multiple choice' : 'Single choice',
    image: Boolean(question.image_asset_id),
    status: question.is_active ? 'Ready' : 'Archived',
    updated: `v${question.version}`,
    options: question.options,
    bankName: bank.name,
  }
}
