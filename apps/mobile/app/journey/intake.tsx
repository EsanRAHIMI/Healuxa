/**
 * Journey intake: a short, NON-CLINICAL preferences form.
 *
 *   startAssessment(kind intake, Idempotency-Key) → submitAssessment(responses, Idempotency-Key)
 *
 * Question codes and answer values are shared with the web app (src/journey/plan.ts). Submitting
 * completes the journey's intake step asynchronously; the journey screen then re-fetches the plan.
 * The only free text is an optional note, with a visible hint that a coordinator reads it.
 */
import { randomUUID } from 'expo-crypto';
import { useRouter } from 'expo-router';
import { useRef, useState } from 'react';
import { I18nManager, View } from 'react-native';

import { ApiError } from '@/api/errors';
import { useAuth } from '@/auth/AuthProvider';
import { errorKey } from '@/hooks/useRemote';
import { type MessageKey, useI18n } from '@/i18n';
import { languageName } from '@/i18n/labels';
import { Choice } from '@/journey/Choice';
import { buildIntakeResponses, INTAKE_OPTIONS, INTAKE_QUESTIONS, type IntakeAnswers, intakeComplete, type IntakeQuestion, NOTES_MAX_LENGTH } from '@/journey/plan';
import { useApi } from '@/services';
import { useTheme } from '@/theme';
import { AppText, Button, Screen, TextField } from '@/ui/primitives';
import { SignedOutPrompt } from '@/ui/SignedOutPrompt';

export default function JourneyIntake() {
  const { t, language } = useI18n();
  const theme = useTheme();
  const api = useApi();
  const auth = useAuth();
  const router = useRouter();
  // Practical defaults the customer can change; timeframe and city are always an explicit choice.
  const [answers, setAnswers] = useState<IntakeAnswers>({ language, practitioner_gender: 'no_preference', visit_mode: 'no_preference' });
  const [notes, setNotes] = useState('');
  const [error, setError] = useState<MessageKey | null>(null);
  const [busy, setBusy] = useState(false);
  const startKey = useRef(randomUUID());
  // One idempotency key per set of answers: a retry replays, edited answers are a new request.
  const submitKeys = useRef<Record<string, string>>({});
  // Kept across retries so a failed submit does not start a second assessment.
  const assessmentId = useRef<string | null>(null);

  const userId = auth.userId;
  if (auth.status !== 'signedIn' || !userId) return <SignedOutPrompt intro={t('journey.signedOutIntro')} />;

  const ready = intakeComplete(answers);
  const optionLabel = (question: IntakeQuestion, value: string) =>
    question === 'language' ? languageName(value, language) : t(`intake.${question}.${value}` as MessageKey);

  const submit = async () => {
    if (!ready) return;
    const responses = buildIntakeResponses(answers, notes);
    setBusy(true);
    setError(null);
    try {
      await auth.withAuth(async (tk) => {
        assessmentId.current ??= (await api.assessments.startIntake(tk, userId, startKey.current)).id;
        await api.assessments.submit(tk, assessmentId.current, responses, (submitKeys.current[JSON.stringify(responses)] ??= randomUUID()));
      });
      router.dismissTo({ pathname: '/journey', params: { notice: 'intake_saved' } });
    } catch (e) {
      setError(errorKey(e instanceof ApiError ? e : new ApiError({ status: 0, code: 'unknown' })));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Screen testID="journey-intake-screen">
      <AppText muted>{t('intake.intro')}</AppText>
      {INTAKE_QUESTIONS.map((question) => (
        <View key={question} style={{ gap: theme.space(2) }} accessibilityRole="radiogroup" accessibilityLabel={t(`intake.${question}`)}>
          <AppText variant="label">{t(`intake.${question}`)}</AppText>
          {INTAKE_OPTIONS[question].map((value) => (
            <Choice
              key={value}
              role="radio"
              label={optionLabel(question, value)}
              selected={answers[question] === value}
              disabled={busy}
              onPress={() => setAnswers((cur) => ({ ...cur, [question]: value }))}
              testID={`intake-${question}-${value}`}
            />
          ))}
        </View>
      ))}
      <TextField
        label={t('intake.notes')}
        hint={t('intake.notesHint')}
        value={notes}
        onChangeText={setNotes}
        multiline
        maxLength={NOTES_MAX_LENGTH}
        editable={!busy}
        style={{
          flex: 1,
          minHeight: 96,
          textAlignVertical: 'top',
          paddingHorizontal: theme.space(4),
          paddingVertical: theme.space(3),
          color: theme.color.text,
          fontSize: theme.font.body,
          textAlign: I18nManager.isRTL ? 'right' : 'left',
        }}
        testID="intake-notes"
      />
      {!ready ? <AppText variant="small" muted testID="intake-required">{t('intake.required')}</AppText> : null}
      {error ? (
        <AppText style={{ color: theme.color.danger }} accessibilityRole="alert" testID="intake-error">
          {t(error)}
        </AppText>
      ) : null}
      <Button label={t('intake.submit')} onPress={submit} busy={busy} disabled={!ready} testID="intake-submit" />
    </Screen>
  );
}
