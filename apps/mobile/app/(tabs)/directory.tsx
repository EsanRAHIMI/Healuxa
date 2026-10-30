import { useRouter } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import { ScrollView } from 'react-native';

import type { PublicResult } from '@/api/client';
import { ApiError } from '@/api/errors';
import type { Facility, Page, Provider, ProviderType } from '@/api/types';
import { useI18n } from '@/i18n';
import { DIRECTORY_LANGUAGES, DIRECTORY_TYPES, facilityTypeLabel, languageName, providerTypeLabel } from '@/i18n/labels';
import { useApi } from '@/services';
import { useTheme } from '@/theme';
import {
  AppText,
  Badge,
  Button,
  Chip,
  EmptyState,
  ErrorState,
  Loading,
  OfflineBanner,
  PressableCard,
  Row,
  Screen,
  TextField,
} from '@/ui/primitives';
import { ProviderCard } from '@/ui/ProviderCard';

const CITIES = ['Dubai', 'Abu Dhabi', 'Sharjah'] as const;

interface ListState<T> {
  items: T[];
  cursor?: string | null;
  hasMore: boolean;
  loading: boolean;
  loadingMore: boolean;
  error?: ApiError;
  fromCache: boolean;
  storedAt?: number;
}

const initial = <T,>(): ListState<T> => ({ items: [], hasMore: false, loading: true, loadingMore: false, fromCache: false });

function usePaged<T>(load: (cursor?: string) => Promise<PublicResult<Page<T>>>, key: string) {
  const [state, setState] = useState<ListState<T>>(initial);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let alive = true;
    setState((s) => ({ ...initial<T>(), items: s.items }));
    load()
      .then((r) => {
        if (alive)
          setState({
            items: r.data.data,
            cursor: r.data.page.next_cursor,
            hasMore: r.data.page.has_more,
            loading: false,
            loadingMore: false,
            fromCache: r.fromCache,
            storedAt: r.storedAt,
          });
      })
      .catch((e: unknown) => {
        if (alive) setState({ ...initial<T>(), loading: false, error: e instanceof ApiError ? e : new ApiError({ status: 0, code: 'unknown' }) });
      });
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, tick]);

  const more = useCallback(async () => {
    if (!state.hasMore || !state.cursor || state.loadingMore) return;
    setState((s) => ({ ...s, loadingMore: true }));
    try {
      const r = await load(state.cursor);
      setState((s) => ({ ...s, items: [...s.items, ...r.data.data], cursor: r.data.page.next_cursor, hasMore: r.data.page.has_more, loadingMore: false }));
    } catch (e) {
      setState((s) => ({ ...s, loadingMore: false, error: e instanceof ApiError ? e : undefined }));
    }
  }, [load, state.cursor, state.hasMore, state.loadingMore]);

  return { ...state, more, reload: () => setTick((n) => n + 1) };
}

/** Directory. Uses provider: searchProviders (type, specialty, language, city, cursor) and searchFacilities. */
export default function Directory() {
  const { t, language } = useI18n();
  const theme = useTheme();
  const api = useApi();
  const router = useRouter();
  const [mode, setMode] = useState<'providers' | 'facilities'>('providers');
  const [specialtyInput, setSpecialtyInput] = useState('');
  const [specialty, setSpecialty] = useState('');
  const [type, setType] = useState<ProviderType | undefined>();
  const [lang, setLang] = useState<string | undefined>();
  const [city, setCity] = useState<string | undefined>();

  // Debounce free-text search so we do not query on every keystroke.
  useEffect(() => {
    const id = setTimeout(() => setSpecialty(specialtyInput.trim()), 350);
    return () => clearTimeout(id);
  }, [specialtyInput]);

  const providers = usePaged<Provider>(
    (cursor) => api.directory.searchProviders({ type, specialty: specialty || undefined, language: lang, city, cursor, limit: 20 }),
    `p|${type}|${specialty}|${lang}|${city}`
  );
  const facilities = usePaged<Facility>(
    (cursor) => api.directory.searchFacilities({ city, cursor, limit: 20 }),
    `f|${city}|${mode}`
  );
  const list = mode === 'providers' ? providers : facilities;
  const filtered = Boolean(type || specialty || lang || city);
  const clear = () => {
    setType(undefined);
    setLang(undefined);
    setCity(undefined);
    setSpecialtyInput('');
  };

  const chips = <V extends string>(label: string, values: readonly V[], current: V | undefined, set: (v: V | undefined) => void, name: (v: V) => string, id: string) => (
    <>
      <AppText variant="label">{label}</AppText>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: theme.space(2) }}>
        <Chip label={t('directory.any')} selected={!current} onPress={() => set(undefined)} testID={`filter-${id}-any`} />
        {values.map((v) => (
          <Chip key={v} label={name(v)} selected={current === v} onPress={() => set(current === v ? undefined : v)} testID={`filter-${id}-${v}`} />
        ))}
      </ScrollView>
    </>
  );

  return (
    <Screen testID="directory-screen" onRefresh={list.reload} refreshing={false}>
      <Row accessibilityRole="tablist">
        <Chip label={t('directory.title')} selected={mode === 'providers'} onPress={() => setMode('providers')} testID="mode-providers" />
        <Chip label={t('directory.facilities')} selected={mode === 'facilities'} onPress={() => setMode('facilities')} testID="mode-facilities" />
      </Row>
      {mode === 'providers' ? (
        <TextField
          label={t('directory.search')}
          hint={t('directory.searchHint')}
          value={specialtyInput}
          onChangeText={setSpecialtyInput}
          autoCorrect={false}
          returnKeyType="search"
          clearButtonMode="while-editing"
          testID="directory-search"
        />
      ) : null}
      {mode === 'providers'
        ? chips(t('directory.type'), DIRECTORY_TYPES, type, setType, (v) => providerTypeLabel(v, language), 'type')
        : null}
      {mode === 'providers'
        ? chips(t('directory.language'), DIRECTORY_LANGUAGES, lang as (typeof DIRECTORY_LANGUAGES)[number] | undefined, setLang, (v) => languageName(v, language), 'lang')
        : null}
      {chips(t('directory.city'), CITIES, city as (typeof CITIES)[number] | undefined, setCity, (v) => v, 'city')}

      {list.fromCache ? <OfflineBanner storedAt={list.storedAt} /> : null}
      {list.loading ? (
        <Loading />
      ) : list.error && !list.items.length ? (
        <ErrorState error={list.error} onRetry={list.reload} />
      ) : !list.items.length ? (
        <EmptyState
          message={t('directory.empty')}
          action={filtered ? <Button kind="link" label={t('directory.clearFilters')} onPress={clear} /> : undefined}
        />
      ) : mode === 'providers' ? (
        providers.items.map((p) => <ProviderCard key={p.id} provider={p} />)
      ) : (
        facilities.items.map((f) => (
          <PressableCard
            key={f.id}
            testID={`facility-card-${f.id}`}
            onPress={() => router.push({ pathname: '/facilities/[id]', params: { id: f.id } })}
            accessibilityLabel={`${f.name}, ${facilityTypeLabel(f.type, language)}`}
          >
            <Row>
              <AppText variant="label">{f.name}</AppText>
              {f.verification_status === 'verified' ? <Badge label={t('common.verified')} icon="shield-checkmark" /> : null}
            </Row>
            <AppText variant="small" muted>
              {facilityTypeLabel(f.type, language)}
            </AppText>
          </PressableCard>
        ))
      )}
      {list.hasMore ? <Button kind="secondary" label={t('directory.loadMore')} onPress={list.more} busy={list.loadingMore} /> : null}
    </Screen>
  );
}
