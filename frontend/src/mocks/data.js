export const adminNav = [
  ['Dashboard', 'dashboard'], ['Exams', 'exams'], ['Question Bank', 'questions'],
  ['Candidates', 'users'], ['Invigilators', 'shield'], ['Results', 'results'],
  ['Reports', 'reports'], ['Audit', 'audit'], ['Settings', 'settings'],
]

export const teacherNav = [
  ['Dashboard', 'dashboard'], ['My Exams', 'exams'], ['Question Bank', 'questions'],
  ['Candidates', 'users'], ['Results', 'results'], ['Profile', 'profile'],
]

export const questions = [
  { text: 'Which process allows green plants to convert light energy into chemical energy?', options: ['Respiration', 'Photosynthesis', 'Transpiration', 'Germination'], correct: 1 },
  { text: 'What is the basic structural and functional unit of life?', options: ['Tissue', 'Organ', 'Cell', 'Nucleus'], correct: 2 },
  { text: 'Which blood cells are primarily responsible for fighting infections?', options: ['Red blood cells', 'Platelets', 'Plasma cells', 'White blood cells'], correct: 3 },
  { text: 'The movement of water molecules through a semi-permeable membrane is called:', options: ['Diffusion', 'Osmosis', 'Active transport', 'Translocation'], correct: 1 },
  { text: 'Which organelle is known as the powerhouse of the cell?', options: ['Ribosome', 'Chloroplast', 'Mitochondrion', 'Golgi body'], correct: 2 },
  { text: 'A group of similar cells performing the same function is called a:', options: ['System', 'Tissue', 'Species', 'Community'], correct: 1 },
  { text: 'Which gas is released as a by-product of photosynthesis?', options: ['Nitrogen', 'Carbon dioxide', 'Hydrogen', 'Oxygen'], correct: 3 },
  { text: 'The largest organ in the human body is the:', options: ['Liver', 'Skin', 'Heart', 'Lung'], correct: 1 },
  { text: 'Which part of a flower develops into a fruit after fertilisation?', options: ['Ovary', 'Anther', 'Sepal', 'Stigma'], correct: 0 },
  { text: 'Animals that feed on both plants and other animals are:', options: ['Herbivores', 'Carnivores', 'Omnivores', 'Decomposers'], correct: 2 },
]

export const recentActivity = [
  ['SS2 Biology Mock', 'Exam published', '12 min ago'],
  ['42 candidate records', 'Imported successfully', '1 hr ago'],
  ['JSS3 Mathematics', 'Results ready to sync', 'Yesterday'],
]

export const sectionContent = {
  exams: {
    title: 'Examinations', description: 'Create, schedule, and monitor school assessments.', action: 'New examination', panelTitle: 'All examinations', panelText: 'Current term · 16 records',
    summary: [['6', 'Active exams', 'success'], ['8', 'Scheduled'], ['12', 'Drafts']],
    columns: ['Examination', 'Subject', 'Class', 'Candidates', 'Status'],
    rows: [['SS2 Biology Mock', 'Biology', 'SS2 Science', '44', { badge: 'In progress', tone: 'success' }], ['JSS3 Mathematics', 'Mathematics', 'JSS3', '88', { badge: 'Scheduled', tone: 'neutral' }], ['SS1 English Language', 'English', 'SS1', '104', { badge: 'Draft', tone: 'warning' }]],
  },
  'my-exams': {
    title: 'My examinations', description: 'Build and manage assessments assigned to your subjects.', action: 'Create exam', panelTitle: 'My exam list', panelText: 'Biology and Basic Science',
    summary: [['2', 'Active now', 'success'], ['3', 'Upcoming'], ['3', 'Completed']],
    columns: ['Examination', 'Class', 'Questions', 'Schedule', 'Status'],
    rows: [['SS2 Biology Mock', 'SS2 Science', '10', '12 Aug, 09:00', { badge: 'In progress', tone: 'success' }], ['Cell Biology Quiz', 'SS1 Science', '20', '14 Aug, 10:00', { badge: 'Scheduled', tone: 'neutral' }], ['Basic Science Test', 'JSS2', '25', '8 Aug, 11:30', { badge: 'Completed', tone: 'neutral' }]],
  },
  'question-bank': {
    title: 'Question bank', description: 'Organize reusable questions by subject, topic, and difficulty.', action: 'Add questions', panelTitle: 'Question library', panelText: '428 questions across 12 subjects',
    summary: [['428', 'Total questions'], ['36', 'Added this month'], ['12', 'Subjects']],
    columns: ['Question preview', 'Subject', 'Topic', 'Difficulty', 'Used'],
    rows: [['Which process allows green plants…', 'Biology', 'Nutrition', { badge: 'Medium', tone: 'neutral' }, '4 exams'], ['Solve for x: 3x + 7 = 22', 'Mathematics', 'Algebra', { badge: 'Easy', tone: 'success' }, '7 exams'], ['Identify the figure of speech…', 'English', 'Literature', { badge: 'Medium', tone: 'neutral' }, '2 exams']],
  },
  candidates: {
    title: 'Candidates', description: 'Review candidate eligibility and live participation.', action: 'Import candidates', panelTitle: 'Candidate register', panelText: 'Current assessment candidates',
    summary: [['376', 'Registered'], ['342', 'Ready', 'success'], ['12', 'Needs attention', 'warning']],
    columns: ['Candidate', 'Admission number', 'Class', 'Exam', 'Status'],
    rows: [['Amina Okeke', 'BFA/2024/0187', 'SS2 Science', 'Biology Mock', { badge: 'Submitted', tone: 'success' }], ['David Balogun', 'BFA/2024/0192', 'SS2 Science', 'Biology Mock', { badge: 'In progress', tone: 'neutral' }], ['Fatima Musa', 'BFA/2024/0201', 'SS2 Science', 'Biology Mock', { badge: 'Not started', tone: 'warning' }]],
  },
  invigilators: {
    title: 'Invigilators', description: 'Assign staff oversight to scheduled examination sessions.', action: 'Assign invigilator', panelTitle: 'Invigilation schedule', panelText: 'Today’s assigned sessions',
    summary: [['8', 'Assigned today'], ['3', 'Sessions active', 'success'], ['1', 'Unassigned', 'warning']],
    columns: ['Invigilator', 'Venue', 'Examination', 'Time', 'Status'],
    rows: [['Mrs. N. Eze', 'ICT Lab A', 'SS2 Biology Mock', '09:00', { badge: 'On duty', tone: 'success' }], ['Mr. K. Bello', 'ICT Lab B', 'JSS3 Mathematics', '11:30', { badge: 'Upcoming', tone: 'neutral' }], ['Unassigned', 'Library Lab', 'SS1 English', '13:00', { badge: 'Needs staff', tone: 'warning' }]],
  },
  results: {
    title: 'Results', description: 'Review component scores before they are synchronized to Weave.', action: 'Sync ready results', panelTitle: 'Recent results', panelText: 'Component scores · not final academic grades',
    summary: [['1,284', 'Submissions'], ['18', 'Pending sync', 'warning'], ['1,266', 'Synchronized', 'success']],
    columns: ['Candidate', 'Examination', 'Raw score', 'Normalized', 'Sync'],
    rows: [['Amina Okeke', 'SS2 Biology Mock', '7 / 10', '70 / 100', { badge: 'Pending', tone: 'warning' }], ['David Balogun', 'SS2 Biology Mock', '9 / 10', '90 / 100', { badge: 'Pending', tone: 'warning' }], ['Zainab Lawal', 'Basic Science Test', '18 / 25', '72 / 100', { badge: 'Synced', tone: 'success' }]],
  },
  reports: {
    title: 'Reports', description: 'Understand participation, completion, and component performance.', action: 'Export report', panelTitle: 'Available reports', panelText: 'Generated from prototype assessment data',
    summary: [['97.8%', 'Completion rate', 'success'], ['71.4', 'Average score'], ['12', 'Reports ready']],
    columns: ['Report', 'Scope', 'Updated', 'Owner', 'Status'],
    rows: [['Term assessment overview', 'Whole school', 'Today, 09:20', 'System', { badge: 'Ready', tone: 'success' }], ['SS2 Biology performance', 'SS2 Science', 'Today, 09:18', 'Chidi Adebayo', { badge: 'Ready', tone: 'success' }], ['Candidate attendance', 'All active exams', 'Yesterday', 'System', { badge: 'Ready', tone: 'success' }]],
  },
  audit: {
    title: 'Audit trail', description: 'Track important actions across the assessment workspace.', panelTitle: 'Recent audit events', panelText: 'Read-only prototype history',
    summary: [['246', 'Events this week'], ['5', 'Staff actors'], ['0', 'Critical flags', 'success']],
    columns: ['Event', 'Actor', 'Resource', 'Date & time', 'Outcome'],
    rows: [['Published examination', 'Amara Okafor', 'SS2 Biology Mock', '12 Aug, 08:42', { badge: 'Success', tone: 'success' }], ['Imported candidates', 'Amara Okafor', '42 records', '12 Aug, 08:16', { badge: 'Success', tone: 'success' }], ['Updated question', 'Chidi Adebayo', 'BIO-Q104', '11 Aug, 16:04', { badge: 'Success', tone: 'success' }]],
  },
  settings: { title: 'Settings', description: 'Prototype installation and assessment preferences.', empty: { title: 'Settings are managed in Weave', text: 'This frontend scaffold does not duplicate unfinished configuration logic. Installation controls will appear here when the backend contract is ready.' } },
  profile: { title: 'Profile', description: 'Your staff identity and assigned teaching context.', panelTitle: 'Teaching profile', panelText: 'Read-only staff details from mock data', summary: [['2', 'Assigned subjects'], ['4', 'Assigned classes'], ['8', 'Created exams']], columns: ['Detail', 'Value', 'Scope'], rows: [['Staff ID', 'BFA/STF/0042', 'Brightfield Academy'], ['Primary subject', 'Biology', 'SS1–SS3'], ['Secondary subject', 'Basic Science', 'JSS1–JSS3']] },
}
