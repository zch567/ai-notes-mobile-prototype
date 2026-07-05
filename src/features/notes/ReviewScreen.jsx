import { useState } from "react";
import { Card } from "../../components/Card";
import { submitReviewAnswers } from "../ai/agentApi";
import { readReviewProgress, saveReviewProgress } from "../../services/localDemoFs";

export function ReviewScreen({ result, onBack }) {
  const { review } = result;
  const [progress, setProgress] = useState(() => readReviewProgress(result.id));
  const [selectedAnswers, setSelectedAnswers] = useState(() => progress.answers || {});
  const [assessment, setAssessment] = useState(() => progress.assessment || null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const [showReviewSet, setShowReviewSet] = useState(false);
  const [reviewSessions, setReviewSessions] = useState(() => normalizeReviewSessions(progress.sessions));
  const hasQuestions = review.questions.length > 0;
  const answerableQuestions = review.questions.filter(isChoiceQuestion);
  const questionResults = assessment?.questionResults || buildLocalQuestionResults(review.questions, selectedAnswers);
  const completedCount = questionResults.filter((item) => item.hasAnswer || item.userAnswer).length;
  const correctCount = questionResults.filter((item) => item.isCorrect).length;
  const localMasteryScore = answerableQuestions.length
    ? Math.round((correctCount / answerableQuestions.length) * 100)
    : review.masteryScore;
  const displayedMasteryScore = assessment?.masteryScore ?? localMasteryScore;
  const displayedWeakPoints = assessment?.weakPoints?.length ? assessment.weakPoints : review.weakPoints;
  const displayedRecommendations = assessment?.reviewSuggestions?.length ? assessment.reviewSuggestions : review.recommendations;
  const wrongExplanations = assessment?.wrongQuestionExplanations || [];
  const isReviewComplete = answerableQuestions.length > 0 && completedCount >= answerableQuestions.length;
  const canSubmit = hasQuestions && answerableQuestions.length > 0 && completedCount >= answerableQuestions.length && !isSubmitting;
  const feedbackText = isReviewComplete
    ? `已完成本次复习，掌握度 ${displayedMasteryScore}%。${displayedWeakPoints.length ? `建议回看：${displayedWeakPoints.slice(0, 2).join("、")}。` : "可以继续追问难点或进入下一份资料。"}`
    : "选择答案后会先在本机判题，点击完成后交给后端生成个性化复习建议。";

  function selectAnswer(question, answer) {
    if (isSubmitting) return;
    setSubmitError("");
    setSelectedAnswers((current) => ({
      ...current,
      [question.id]: nextSelectedAnswer(question, current[question.id], answer),
    }));
  }

  async function completeReview() {
    if (!canSubmit) return;
    const localResults = buildLocalQuestionResults(review.questions, selectedAnswers);
    const nextProgress = {
      answers: selectedAnswers,
      answeredQuestionIds: localResults.filter((item) => item.hasAnswer).map((item) => item.questionId),
      localQuestionResults: localResults,
      sessions: reviewSessions,
      lastReviewedAt: new Date().toISOString(),
    };
    const localSession = createReviewSession({
      id: createSessionId(),
      result,
      answers: selectedAnswers,
      questionResults: localResults,
      assessment: null,
      fallbackSuggestions: displayedRecommendations,
      submittedAt: nextProgress.lastReviewedAt,
    });
    const sessionsWithLocal = upsertSession(reviewSessions, localSession);
    const localProgress = {
      ...nextProgress,
      sessions: sessionsWithLocal,
    };
    setReviewSessions(sessionsWithLocal);
    setProgress(localProgress);
    saveReviewProgress(result.id, localProgress);

    setIsSubmitting(true);
    setSubmitError("");
    try {
      const remoteAssessment = await submitReviewAnswers({
        resultId: result.id,
        answers: answerableQuestions.map((question) => ({
          questionId: question.id,
          answer: serializeAnswerForSubmit(question, selectedAnswers[question.id]),
        })),
      });
      const completedAt = new Date().toISOString();
      const remoteSession = createReviewSession({
        id: localSession.id,
        result,
        answers: selectedAnswers,
        questionResults: remoteAssessment.questionResults || localResults,
        assessment: remoteAssessment,
        fallbackSuggestions: displayedRecommendations,
        submittedAt: completedAt,
      });
      const sessionsWithRemote = upsertSession(sessionsWithLocal, remoteSession);
      const completedProgress = {
        ...localProgress,
        assessment: remoteAssessment,
        sessions: sessionsWithRemote,
        lastReviewedAt: completedAt,
      };
      setAssessment(remoteAssessment);
      setReviewSessions(sessionsWithRemote);
      setProgress(completedProgress);
      saveReviewProgress(result.id, completedProgress);
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : "复习建议生成失败，请稍后重试。");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex-none border-b border-slate-200 bg-white px-5 py-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <button onClick={onBack} className="text-[13px] font-semibold text-blue-600">
              返回
            </button>
            <h1 className="mt-2 text-[24px] font-semibold tracking-tight text-slate-950">复习评估</h1>
          </div>
          <button
            type="button"
            onClick={() => setShowReviewSet(true)}
            className="mt-1 rounded-full bg-slate-900 px-3 py-2 text-[12px] font-semibold text-white shadow-sm active:scale-[0.98]"
          >
            题集 {reviewSessions.length ? reviewSessions.length : ""}
          </button>
        </div>
        <p className="mt-1 text-[13px] leading-5 text-slate-500">由 AgentResult.review 统一渲染。</p>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5">
        <div className="space-y-4">
          <Card title="复习题" subtitle="Questions">
            <div className="space-y-3">
              {hasQuestions ? review.questions.map((item, index) => (
                <div key={item.id} className="rounded-2xl bg-slate-50 p-4">
                  <div className="mb-2 flex flex-wrap gap-2">
                    <span className="rounded-full bg-blue-50 px-2.5 py-1 text-[11px] font-semibold text-blue-700">
                      {questionTypeLabel(item.type)}
                    </span>
                    {isReviewComplete ? (
                      <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${
                        isQuestionCorrect(questionResults, item.id)
                          ? "bg-emerald-50 text-emerald-700"
                          : "bg-rose-50 text-rose-700"
                      }`}>
                        {isQuestionCorrect(questionResults, item.id) ? "已答对" : "需订正"}
                      </span>
                    ) : null}
                    {item.relatedNoteId ? (
                      <span className="rounded-full bg-white px-2.5 py-1 text-[11px] font-semibold text-slate-500 ring-1 ring-slate-200">
                        关联笔记 {item.relatedNoteId}
                      </span>
                    ) : null}
                  </div>
                  <p className="text-[14px] font-semibold text-slate-900">{index + 1}. {item.question}</p>
                  {item.options ? (
                    <div className="mt-3 grid gap-2">
                      {item.options.map((option) => (
                        <button
                          key={option}
                          type="button"
                          disabled={isSubmitting}
                          onClick={() => selectAnswer(item, option)}
                          className={answerOptionClassName({
                            option,
                            question: item,
                            selectedAnswer: selectedAnswers[item.id],
                            showResult: isReviewComplete,
                          })}
                        >
                          {option}
                        </button>
                      ))}
                    </div>
                  ) : null}
                  {isReviewComplete ? (
                    <div className="mt-3 rounded-2xl bg-white px-3 py-3 text-[13px] leading-6 text-slate-600 ring-1 ring-slate-200">
                      <p>
                        标准答案：<span className="font-semibold text-slate-900">{normalizeQuestionAnswer(item)}</span>
                      </p>
                      {item.explanation ? <p className="mt-1">{item.explanation}</p> : null}
                    </div>
                  ) : null}
                </div>
              )) : (
                <EmptyState text="当前结果没有返回复习题。请检查真实后端的 review.questions 字段。" />
              )}
            </div>
          </Card>

          <Card title="掌握度" subtitle="Evaluation">
            <div className="flex items-end justify-between">
              <span className="text-[42px] font-semibold tracking-tight text-blue-600">{displayedMasteryScore}%</span>
              <span className="mb-2 text-[13px] font-semibold text-slate-400">Mastery score</span>
            </div>
            <div className="mt-3 h-2 overflow-hidden rounded-full bg-blue-100">
              <div className="h-full rounded-full bg-blue-600" style={{ width: `${displayedMasteryScore}%` }} />
            </div>
            <button
              onClick={completeReview}
              disabled={!canSubmit}
              className={`mt-4 w-full rounded-2xl px-4 py-3 text-[13px] font-semibold transition ${
                canSubmit ? "bg-slate-900 text-white active:scale-[0.99]" : "bg-slate-200 text-slate-400"
              }`}
            >
              {isSubmitting ? "正在提交做题情况" : "完成本次复习"}
            </button>
            <div className={`mt-3 rounded-2xl px-3 py-3 text-[12px] leading-5 ${
              isReviewComplete ? "bg-emerald-50 text-emerald-800" : "bg-slate-50 text-slate-500"
            }`}>
              {feedbackText}
            </div>
            {submitError ? (
              <p className="mt-3 rounded-2xl bg-rose-50 px-3 py-2 text-[12px] leading-5 text-rose-700">
                {submitError}
              </p>
            ) : null}
            {progress.lastReviewedAt ? (
              <p className="mt-3 text-[12px] leading-5 text-slate-500">
                最近复习：{new Date(progress.lastReviewedAt).toLocaleString()}
              </p>
            ) : null}
            {isReviewComplete ? (
              <div className="mt-3 grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setShowReviewSet(true)}
                  className="rounded-2xl bg-white px-3 py-2 text-[12px] font-semibold text-slate-700 ring-1 ring-slate-200 active:bg-slate-50"
                >
                  查看复习题集
                </button>
                <button
                  type="button"
                  disabled
                  className="rounded-2xl bg-slate-100 px-3 py-2 text-[12px] font-semibold text-slate-400"
                >
                  重新出题待接入
                </button>
              </div>
            ) : null}
          </Card>

          <Card
            title={
              <span className="inline-flex items-center gap-2">
                薄弱点与建议
                {isSubmitting ? <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-amber-300 border-t-amber-700" /> : null}
              </span>
            }
            subtitle={isSubmitting ? "AI Thinking" : "Recommendation"}
          >
            <div className="space-y-3">
              {isSubmitting ? (
                <div className="rounded-2xl bg-amber-50 px-3 py-3 text-[13px] leading-5 text-amber-900">
                  后端已收到本次做题情况，大模型正在分析错因并生成复习建议。
                </div>
              ) : null}
              <div>
                <p className="text-[12px] font-semibold uppercase tracking-[0.18em] text-slate-400">Weak Points</p>
                {displayedWeakPoints.length ? (
                  <p className="mt-1 text-[14px] font-semibold text-slate-900">{displayedWeakPoints.join("、")}</p>
                ) : (
                  <p className="mt-1 text-[13px] leading-5 text-slate-500">暂无薄弱点。后端可在 review.weakPoints 中返回知识点名称。</p>
                )}
              </div>
              {wrongExplanations.length ? (
                <div className="space-y-2">
                  <p className="text-[12px] font-semibold uppercase tracking-[0.18em] text-slate-400">Wrong Answers</p>
                  {wrongExplanations.map((item) => (
                    <div key={item.questionId || item.knowledgePoint || item.mistakeReason} className="rounded-2xl bg-rose-50 px-3 py-3 text-[13px] leading-5 text-rose-900">
                      <p className="font-semibold">{item.knowledgePoint || item.questionId || "错题解析"}</p>
                      <p className="mt-1">{item.mistakeReason}</p>
                      {item.correctThinking ? <p className="mt-1 text-rose-800">正确思路：{item.correctThinking}</p> : null}
                      {item.remediation ? <p className="mt-1 text-rose-800">补救动作：{item.remediation}</p> : null}
                    </div>
                  ))}
                </div>
              ) : null}
              <div className="space-y-2">
                {displayedRecommendations.length ? displayedRecommendations.map((item) => (
                  <p key={item} className="rounded-2xl bg-amber-50 px-3 py-2 text-[13px] leading-5 text-amber-900">
                    {item}
                  </p>
                )) : (
                  <EmptyState text="暂无复习建议。建议至少返回一个可操作动作，比如重读某个来源片段或重做某类题。" />
                )}
              </div>
            </div>
          </Card>
        </div>
      </div>

      {showReviewSet ? (
        <ReviewSetPanel
          sessions={reviewSessions}
          canRegenerateReview={false}
          onClose={() => setShowReviewSet(false)}
        />
      ) : null}
    </div>
  );
}

function ReviewSetPanel({ sessions, canRegenerateReview, onClose }) {
  return (
    <div className="absolute inset-0 z-30 flex flex-col bg-white">
      <div className="flex-none border-b border-slate-200 px-5 py-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-[12px] font-semibold uppercase tracking-[0.2em] text-slate-400">Review Set</p>
            <h2 className="mt-1 text-[22px] font-semibold tracking-tight text-slate-950">复习题集</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full bg-slate-100 px-3 py-2 text-[12px] font-semibold text-slate-600 active:bg-slate-200"
          >
            关闭
          </button>
        </div>
        <p className="mt-2 text-[13px] leading-5 text-slate-500">
          保存每次作答、判题结果和当次复习建议。
        </p>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-5 py-5">
        {sessions.length ? (
          <div className="space-y-4">
            {sessions.map((session, index) => (
              <div key={session.id} className="rounded-[24px] border border-slate-200 bg-white p-4 shadow-sm">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-[12px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                      第 {sessions.length - index} 次复习
                    </p>
                    <p className="mt-1 text-[16px] font-semibold text-slate-950">
                      掌握度 {session.masteryScore}% · {session.correctCount}/{session.totalCount}
                    </p>
                  </div>
                  <span className="rounded-full bg-blue-50 px-2.5 py-1 text-[11px] font-semibold text-blue-700">
                    {formatSessionTime(session.submittedAt)}
                  </span>
                </div>

                <div className="mt-3 space-y-2">
                  {session.questionResults.map((item, itemIndex) => (
                    <div key={item.questionId || itemIndex} className="rounded-2xl bg-slate-50 px-3 py-3">
                      <div className="flex items-start justify-between gap-2">
                        <p className="text-[13px] font-semibold leading-5 text-slate-900">
                          {itemIndex + 1}. {item.question}
                        </p>
                        <span className={`shrink-0 rounded-full px-2 py-1 text-[10px] font-semibold ${
                          item.isCorrect ? "bg-emerald-50 text-emerald-700" : "bg-rose-50 text-rose-700"
                        }`}>
                          {item.isCorrect ? "正确" : "订正"}
                        </span>
                      </div>
                      <p className="mt-2 text-[12px] leading-5 text-slate-500">
                        我的答案：{item.userAnswer || "未作答"}
                      </p>
                      <p className="text-[12px] leading-5 text-slate-500">
                        标准答案：{item.correctAnswer || "无"}
                      </p>
                    </div>
                  ))}
                </div>

                {session.wrongQuestionExplanations.length ? (
                  <div className="mt-3 space-y-2">
                    {session.wrongQuestionExplanations.map((item) => (
                      <p key={item.questionId || item.knowledgePoint || item.mistakeReason} className="rounded-2xl bg-rose-50 px-3 py-2 text-[12px] leading-5 text-rose-900">
                        {item.knowledgePoint ? `${item.knowledgePoint}：` : ""}{item.remediation || item.mistakeReason || item.correctThinking}
                      </p>
                    ))}
                  </div>
                ) : null}

                <div className="mt-3 space-y-2">
                  {session.reviewSuggestions.map((item) => (
                    <p key={item} className="rounded-2xl bg-amber-50 px-3 py-2 text-[12px] leading-5 text-amber-900">
                      {item}
                    </p>
                  ))}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyState text="还没有复习记录。完成本次复习后，题目、答案和建议会自动放入题集。" />
        )}

        <div className="mt-4 rounded-2xl bg-slate-50 px-3 py-3 text-[12px] leading-5 text-slate-500">
          {canRegenerateReview
            ? "后端已支持重新出题，可在完成复习后生成下一套题。"
            : "后端当前尚未实现 regenerate-review 或 /api/agent/edit，重新出题按钮将在接口接入后开放。"}
        </div>
      </div>
    </div>
  );
}

function EmptyState({ text }) {
  return (
    <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-4 text-[13px] leading-6 text-slate-500">
      {text}
    </div>
  );
}

function questionTypeLabel(type) {
  const labels = {
    "single-choice": "单选题",
    "multiple-choice": "多选题",
    judgement: "判断题",
    "short-answer": "简答题",
    "concept-explanation": "概念解释",
    application: "应用理解",
  };
  return labels[type] || type || "复习题";
}

function isChoiceQuestion(question) {
  return ["single-choice", "single_choice", "multiple-choice", "multiple_choice"].includes(question?.type) && Array.isArray(question?.options) && question.options.length > 0;
}

function buildLocalQuestionResults(questions, answers) {
  return questions.map((question) => {
    const answerValue = answers?.[question.id];
    const userItems = isMultipleChoiceQuestion(question) ? normalizeMultiChoiceAnswer(answerValue, question.options) : [];
    const correctItems = isMultipleChoiceQuestion(question) ? normalizeMultiChoiceAnswer(question.answer, question.options) : [];
    const userAnswer = isMultipleChoiceQuestion(question) ? userItems.join("; ") : normalizeChoiceAnswer(answerValue, question.options);
    const correctAnswer = isMultipleChoiceQuestion(question) ? correctItems.join("; ") : normalizeChoiceAnswer(question.answer, question.options);
    return {
      questionId: question.id,
      question: question.question,
      userAnswer,
      correctAnswer,
      isCorrect: isChoiceQuestion(question) && (
        isMultipleChoiceQuestion(question) ? choiceSetEqual(userItems, correctItems) : choiceEqual(userAnswer, correctAnswer)
      ),
      hasAnswer: isMultipleChoiceQuestion(question) ? userItems.length > 0 : Boolean(userAnswer),
    };
  });
}

function isQuestionCorrect(questionResults, questionId) {
  return Boolean(questionResults.find((item) => item.questionId === questionId)?.isCorrect);
}

function answerOptionClassName({ option, question, selectedAnswer, showResult }) {
  const isSelected = isAnswerSelected(question, selectedAnswer, option);
  const isCorrect = isMultipleChoiceQuestion(question)
    ? normalizeMultiChoiceAnswer(question.answer, question.options).some((item) => choiceEqual(option, item))
    : choiceEqual(option, normalizeChoiceAnswer(question.answer, question.options));
  const base = "rounded-2xl border px-3 py-2 text-left text-[13px] leading-5 transition";

  if (showResult && isCorrect) return `${base} border-emerald-300 bg-emerald-50 text-emerald-800`;
  if (showResult && isSelected && !isCorrect) return `${base} border-rose-300 bg-rose-50 text-rose-800`;
  if (isSelected) return `${base} border-blue-300 bg-blue-50 text-blue-800`;
  return `${base} border-slate-200 bg-white text-slate-600 active:bg-slate-100`;
}

function normalizeChoiceAnswer(answer, options = []) {
  const value = String(Array.isArray(answer) ? answer[0] : answer || "").trim();
  if (!value) return "";
  const label = value.replace(/[.、:：]$/, "").toUpperCase();
  if (/^[A-D]$/.test(label)) {
    const index = label.charCodeAt(0) - "A".charCodeAt(0);
    if (index >= 0 && index < options.length) return options[index];
  }
  return options.find((option) => value === option || value.includes(option) || option.includes(value)) || value;
}

function normalizeMultiChoiceAnswer(answer, options = []) {
  const rawValues = Array.isArray(answer) ? answer : [answer];
  const normalized = [];
  rawValues.forEach((value) => {
    String(value || "")
      .replace(/；/g, ";")
      .replace(/，/g, ",")
      .replace(/;/g, ",")
      .split(",")
      .forEach((part) => {
        const item = normalizeChoiceAnswer(part, options);
        if (item && !normalized.some((current) => choiceEqual(current, item))) {
          normalized.push(item);
        }
      });
  });
  return normalized;
}

function choiceEqual(left, right) {
  const clean = (value) => String(value || "").replace(/[^\dA-Za-z\u4e00-\u9fff]/g, "").toLowerCase();
  return Boolean(clean(left)) && clean(left) === clean(right);
}

function choiceSetEqual(left, right) {
  const cleanSet = (items) => new Set(items.map((item) => String(item || "").replace(/[^\dA-Za-z\u4e00-\u9fff]/g, "").toLowerCase()).filter(Boolean));
  const leftSet = cleanSet(left);
  const rightSet = cleanSet(right);
  return leftSet.size > 0 && leftSet.size === rightSet.size && [...leftSet].every((item) => rightSet.has(item));
}

function isMultipleChoiceQuestion(question) {
  return ["multiple-choice", "multiple_choice"].includes(question?.type);
}

function nextSelectedAnswer(question, currentAnswer, option) {
  if (!isMultipleChoiceQuestion(question)) return option;
  const currentItems = normalizeMultiChoiceAnswer(currentAnswer, question.options);
  const exists = currentItems.some((item) => choiceEqual(item, option));
  return exists ? currentItems.filter((item) => !choiceEqual(item, option)) : [...currentItems, option];
}

function isAnswerSelected(question, selectedAnswer, option) {
  if (isMultipleChoiceQuestion(question)) {
    return normalizeMultiChoiceAnswer(selectedAnswer, question.options).some((item) => choiceEqual(item, option));
  }
  return choiceEqual(selectedAnswer, option);
}

function serializeAnswerForSubmit(question, answer) {
  if (isMultipleChoiceQuestion(question)) {
    return normalizeMultiChoiceAnswer(answer, question.options).join(",");
  }
  return normalizeChoiceAnswer(answer, question.options);
}

function normalizeQuestionAnswer(question) {
  return isMultipleChoiceQuestion(question)
    ? normalizeMultiChoiceAnswer(question.answer, question.options).join("; ")
    : normalizeChoiceAnswer(question.answer, question.options);
}

function createReviewSession({ id, result, answers, questionResults, assessment, fallbackSuggestions, submittedAt }) {
  const normalizedResults = questionResults.map((item) => ({
    questionId: String(item.questionId || ""),
    question: String(item.question || findQuestion(result.review.questions, item.questionId)?.question || ""),
    userAnswer: String(item.userAnswer || answers?.[item.questionId] || ""),
    correctAnswer: String(item.correctAnswer || normalizeQuestionAnswer(findQuestion(result.review.questions, item.questionId))),
    isCorrect: Boolean(item.isCorrect),
  }));
  const correctCount = normalizedResults.filter((item) => item.isCorrect).length;
  const totalCount = normalizedResults.length;

  return {
    id,
    submittedAt,
    topic: result.topic,
    masteryScore: Math.round(Number(assessment?.masteryScore ?? (totalCount ? correctCount / totalCount * 100 : 0))),
    correctCount: Number(assessment?.correctCount ?? correctCount),
    totalCount: Number(assessment?.totalCount ?? totalCount),
    questionResults: normalizedResults,
    wrongQuestionExplanations: normalizeExplanationList(assessment?.wrongQuestionExplanations),
    weakPoints: normalizeTextList(assessment?.weakPoints),
    reviewSuggestions: normalizeTextList(assessment?.reviewSuggestions).length
      ? normalizeTextList(assessment?.reviewSuggestions)
      : normalizeTextList(fallbackSuggestions),
  };
}

function normalizeReviewSessions(value) {
  return Array.isArray(value) ? value.filter((item) => item && typeof item === "object") : [];
}

function upsertSession(sessions, session) {
  return [session, ...sessions.filter((item) => item.id !== session.id)].slice(0, 20);
}

function createSessionId() {
  return `review-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;
}

function findQuestion(questions, questionId) {
  return questions.find((item) => item.id === questionId) || {};
}

function normalizeTextList(value) {
  return Array.isArray(value) ? value.map((item) => String(item || "").trim()).filter(Boolean) : [];
}

function normalizeExplanationList(value) {
  return Array.isArray(value) ? value.filter((item) => item && typeof item === "object") : [];
}

function formatSessionTime(value) {
  const time = Date.parse(value || "");
  if (!time) return "刚刚";
  return new Date(time).toLocaleString();
}
