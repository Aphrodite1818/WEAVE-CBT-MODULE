# Question Builder Design QA

- Source visual truth: user-provided teacher question-creation reference screenshot in this conversation (desktop, expanded sidebar).
- Implementation screenshot: `design-qa-question-builder.png`.
- Viewport: 1320 x 656 CSS px, device scale factor 1.
- Source pixels: 1680 x 941. Implementation pixels: 1320 x 656. Comparison was composition- and behavior-based because the supplied reference and available browser viewport have different aspect ratios.
- State: expanded teacher sidebar, create-question editor, and open Add instruction modal; preview verified as a separate in-flow screen that preserves the unsaved draft.

## Full-view comparison evidence

- The form keeps the reference's two-column authoring composition with Question content on the left and compact Answer options on the right.
- Cancel, Save & create another, and Save & close remain grouped at the top without wrapping at the verified viewport.
- The expanded sidebar is 220 px wide, leaving the authoring canvas visibly wider than the original 248 px shell.
- Answer rows retain a consistent radio, letter, text, image-upload, and delete sequence without an image-URL field.
- Preview is opened from a dedicated button directly below Answer options and replaces the editor with a focused student-view screen.
- Optional instruction authoring stays compact behind a branded Add instruction button instead of permanently increasing the form height.

## Focused region comparison evidence

- Typography: page title, card titles, field labels, input text, and actions are visibly larger than the original implementation and remain hierarchically distinct.
- Spacing: card gutters, row gaps, control heights, and the two-column gap remain consistent with the sidebar open.
- Colors: all surfaces and actions use the active tenant branding tokens; no fixed screenshot palette was introduced.
- Images: existing tenant logo and application icon library are preserved. Image controls invoke the real local upload contract.
- Controls: textareas and text inputs use custom appearance, focus, caret, and scrollbar styling with native resize handles removed.
- Copy: labels are concise and reflect actual behavior, including live preview and local image uploads.
- Modal contrast: the instruction dialog uses a soft neutral shell, a white editor panel, and fully opaque tenant-branded actions. The portal inherits dashboard theme tokens, so Save instruction remains readable under tenant branding.
- Image feedback: prompt and answer uploads render in compact contained thumbnails with centered intrinsic sizing, inner padding, and no crop for square, portrait, or landscape assets.

## Interaction evidence

- Tested prompt entry and functional Bold formatting.
- Tested answer text entry and single-choice correct-answer selection.
- Tested opening the dedicated preview page and returning with its filled, right-aligned Back to editor button without losing the draft.
- Tested opening and cancelling the instruction modal; Cancel discards the modal draft, Escape is wired to close, and focus returns to Add instruction.
- Confirmed the teacher preview no longer shows the student-only Mark for review control, and instruction text resolves to the active tenant primary color (`rgb(190, 18, 60)` in the verified tenant).
- Added and passed a React Strict Mode regression test for both prompt and option image previews. It verifies the committed `<img>` sources use live object URLs that have not been revoked.
- Checked browser console. Reported warnings and errors came from browser extensions; no application error was produced by the instruction interaction.
- Focused ESLint passed for the changed React files.
- Staff production build passed.

## Comparison history

1. Initial implementation retained a 248 px sidebar, stacked setup/content cards, tall answer editors, and an always-visible preview.
2. Reworked the form into two authoring columns, compacted answer rows, and added icon-only image upload without an image-URL field.
3. Consolidated question-image upload/removal into the prompt toolbar, removed the redundant upload panel, and moved preview to a dedicated screen with a visible return action.
4. Reduced the expanded sidebar to 220 px and tightened its internal spacing; post-fix browser evidence confirms the two-column editor remains comfortable at 1320 px with the sidebar open.
5. Replaced the compressed inline instruction input with an on-demand modal. The first modal capture exposed missing tenant token inheritance and an unreadable Save action; mounting the portal inside the themed app root fixed the contrast. The revised capture shows a visible burgundy Save instruction button on a soft neutral modal surface.
6. Fixed broken local image feedback caused by object URLs being created during render and revoked by Strict Mode cleanup. Object URLs are now created per effect mount, and both prompt and option thumbnails use uncropped intrinsic containment.

## Findings

- No actionable P0, P1, or P2 issues remain in the verified desktop state.
- P3: native textarea formatting stores lightweight markers in the authoring field; the live preview and student exam render those markers as formatted content.

## Implementation checklist

- [x] Larger, readable form typography.
- [x] Two-column layout with expanded sidebar.
- [x] Compact right-side answer rows.
- [x] Icon-only option image upload.
- [x] Functional formatting toolbar.
- [x] Question-image upload and removal in the prompt toolbar.
- [x] Dedicated preview screen and return action.
- [x] Narrower global teacher sidebar.
- [x] White account-control surface.
- [x] Compact Add instruction trigger and formatted modal editor.
- [x] Visible Cancel and Save instruction actions with tenant-aware contrast.
- [x] Student-only Mark for review removed from teacher preview.
- [x] Tenant-branded instruction text in preview.
- [x] Immediate, uncropped prompt and option image feedback.

final result: passed
