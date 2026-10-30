/**
 * New concierge request. Uses concierge: createConciergeCase (Idempotency-Key).
 * The case model is deliberately non-clinical: the free-text field carries a visible warning not to
 * enter health information, and nothing else asks for it.
 */
import { randomUUID } from 'expo-crypto';
import { useRouter } from 'expo-router';
import { useRef, useState } from 'react';
import { ScrollView } from 'react-native';

import { ApiError } from '@/api/errors';
import type { CaseCategory } from '@/api/types';
import { useAuth } from '@/auth/AuthProvider';
import { errorKey } from '@/hooks/useRemote';
import { type MessageKey, useI18n } from '@/i18n';
import { DIRECTORY_LANGUAGES, languageName } from '@/i18n/labels';
import { useApi } from '@/services';
import { useTheme } from '@/theme';
import { AppText, Button, Card, Chip, Row, Screen, TextField } from '@/ui/primitives';
import { SignedOutPrompt } from '@/ui/SignedOutPrompt';

const CATEGORIES: CaseCategory[] = ['medical_travel', 'specialist_search', 'second_opinion_coordination', 'logistics', 'other'];
const DATE = /^\d{4}-\d{2}-\d{2}$/;

export default function NewConciergeCase() {
  const { t, language } = useI18n();
  const theme = useTheme();
  const api = useApi();
  const auth = useAuth();
  const router = useRouter();
  const [category, setCategory] = useState<CaseCategory | null>(null);
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [city, setCity] = useState('');
  const [langs, setLangs] = useState<string[]>([language]);
  const [note, setNote] = useState('');
  const [error, setError] = useState<MessageKey | null>(null);
  const [busy, setBusy] = useState(false);
  const key = useRef(randomUUID());

  if (auth.status !== 'signedIn') return <SignedOutPrompt />;

  const badDate = (v: string) => v.length > 0 && !DATE.test(v);
  const submit = async () => {
    if (!category || badDate(start) || badDate(end)) return;
    setBusy(true);
    setError(null);
    try {
      const created = await auth.withAuth((tk) =>
        api.concierge.create(
          tk,
          {
            category,
            preferred_start_date: start || null,
            preferred_end_date: end || null,
            destination_city: city.trim() || null,
            languages: langs,
            needs_note: note.trim() || null,
          },
          key.current
        )
      );
      router.replace({ pathname: '/concierge/[id]', params: { id: created.id } });
    } catch (e) {
      setError(errorKey(e instanceof ApiError ? e : new ApiError({ status: 0, code: 'unknown' })));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Screen testID="concierge-new-screen">
      <AppText variant="label">{t('concierge.category')}</AppText>
      <Row>
        {CATEGORIES.map((c) => (
          <Chip key={c} label={t(`concierge.category.${c}` as MessageKey)} selected={category === c} onPress={() => setCategory(c)} testID={`category-${c}`} />
        ))}
      </Row>
      <TextField label={t('concierge.startDate')} value={start} onChangeText={setStart} placeholder="2026-12-01" keyboardType="numbers-and-punctuation" error={badDate(start) ? t('concierge.dateInvalid') : undefined} />
      <TextField label={t('concierge.endDate')} value={end} onChangeText={setEnd} placeholder="2026-12-07" keyboardType="numbers-and-punctuation" error={badDate(end) ? t('concierge.dateInvalid') : undefined} />
      <TextField label={t('concierge.city')} value={city} onChangeText={setCity} maxLength={120} />
      <AppText variant="label">{t('concierge.languages')}</AppText>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: theme.space(2) }}>
        {DIRECTORY_LANGUAGES.map((l) => (
          <Chip
            key={l}
            label={languageName(l, language)}
            selected={langs.includes(l)}
            onPress={() => setLangs((cur) => (cur.includes(l) ? cur.filter((x) => x !== l) : [...cur, l].slice(0, 5)))}
          />
        ))}
      </ScrollView>
      <Card style={{ borderColor: theme.color.danger }}>
        <AppText variant="small">{t('concierge.noteWarning')}</AppText>
      </Card>
      <TextField label={t('concierge.note')} value={note} onChangeText={setNote} multiline maxLength={2000} style={{ minHeight: 96, textAlignVertical: 'top' }} testID="concierge-note" />
      {error ? <AppText style={{ color: theme.color.danger }} accessibilityRole="alert">{t(error)}</AppText> : null}
      <Button label={t('concierge.submit')} onPress={submit} busy={busy} disabled={!category} testID="concierge-submit" />
    </Screen>
  );
}
