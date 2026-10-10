import { Canvas, Picture, Skia, type SkImage } from '@shopify/react-native-skia';
import { Redirect, Stack } from 'expo-router';
import { useEffect, useMemo, useReducer, useState } from 'react';
import { ActivityIndicator, type LayoutRectangle, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import filters from '../../../assets/filters.json';
import { fitScale } from '../src/editor/crop';
import { canRedo, canUndo, committed, editorReducer, initialEditorState, isDirty } from '../src/editor/history';
import { loadLutAtlases } from '../src/editor/luts';
import { type Adjustments, CROPS, IDENTITY, LOOK_INTENSITY, LOOKS, SLIDERS } from '../src/editor/model';
import { createRenderer, type Renderer } from '../src/editor/render';
import { ExportError, shareExport, writeExport } from '../src/media/exportImage';
import { useSession } from '../src/session';
import { Button } from '../src/ui/Button';
import { LabeledSlider } from '../src/ui/LabeledSlider';
import { colors, radii, space, type } from '../src/ui/theme';

type Tab = 'adjust' | 'looks' | 'crop' | 'ai';
const TABS: readonly { readonly id: Tab; readonly label: string }[] = [
  { id: 'adjust', label: 'Adjust' },
  { id: 'looks', label: 'Looks' },
  { id: 'crop', label: 'Crop' },
  { id: 'ai', label: 'AI' },
];

type ExportState = { readonly kind: 'idle' } | { readonly kind: 'rendering' } | { readonly kind: 'error'; readonly message: string };

let sharedRenderer: Renderer | null = null;
function getRenderer(): Renderer {
  sharedRenderer ??= createRenderer(Skia, loadLutAtlases());
  return sharedRenderer;
}

const nextFrame = () => new Promise<void>((resolve) => requestAnimationFrame(() => resolve()));

export default function Editor() {
  const { source } = useSession();
  const [image, setImage] = useState<SkImage | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [state, dispatch] = useReducer(editorReducer, undefined, initialEditorState);
  const [tab, setTab] = useState<Tab>('adjust');
  const [compareOn, setCompareOn] = useState(false);
  const [holding, setHolding] = useState(false);
  const [box, setBox] = useState<LayoutRectangle | null>(null);
  const [exportState, setExportState] = useState<ExportState>({ kind: 'idle' });

  useEffect(() => {
    if (source === null) return;
    let live = true;
    setImage(null);
    setLoadError(false);
    Skia.Data.fromURI(source.uri)
      .then((data) => {
        const img = Skia.Image.MakeImageFromEncoded(data);
        if (!live) return;
        if (img === null) setLoadError(true);
        else setImage(img);
      })
      .catch(() => live && setLoadError(true));
    return () => {
      live = false;
    };
  }, [source]);

  const showBefore = compareOn || holding;
  const shown: Adjustments = useMemo(
    () => (showBefore ? { ...IDENTITY, crop: state.candidate.crop } : state.candidate),
    [showBefore, state.candidate],
  );

  const view = useMemo(() => {
    if (image === null || box === null || box.width <= 0 || box.height <= 0) return null;
    const renderer = getRenderer();
    const rect = renderer.outputRect(image, shown);
    const scale = fitScale(box, rect);
    return { picture: renderer.picture(image, shown, scale), width: rect.width * scale, height: rect.height * scale };
  }, [image, box, shown]);

  if (source === null) return <Redirect href="/" />;

  const dirty = isDirty(state);
  const exporting = exportState.kind === 'rendering';

  async function exportCommitted() {
    if (image === null) return;
    setExportState({ kind: 'rendering' });
    await nextFrame();
    try {
      const renderer = getRenderer();
      const jpeg = renderer.encodeJpeg(renderer.renderFull(image, committed(state)), 95);
      await shareExport(writeExport(jpeg));
      setExportState({ kind: 'idle' });
    } catch (e) {
      setExportState({ kind: 'error', message: e instanceof ExportError ? e.message : 'The photo could not be exported. Try again.' });
    }
  }

  const exportRect = image ? getRenderer().outputRect(image, committed(state)) : null;

  return (
    <View style={styles.screen}>
      <Stack.Screen
        options={{
          headerRight: () => (
            <Button
              label="Export"
              variant="quiet"
              disabled={dirty || exporting || image === null}
              hint={dirty ? 'Apply or discard your changes first' : 'Saves the edited photo at full size'}
              onPress={() => void exportCommitted()}
            />
          ),
        }}
      />
      <Pressable
        style={styles.stage}
        onLayout={(e) => setBox(e.nativeEvent.layout)}
        onPressIn={() => setHolding(true)}
        onPressOut={() => setHolding(false)}
        accessible={false}
      >
        {view ? (
          <Canvas
            style={{ width: view.width, height: view.height }}
            accessibilityRole="image"
            accessibilityLabel={showBefore ? 'Original photo' : 'Edited photo preview'}
          >
            <Picture picture={view.picture} />
          </Canvas>
        ) : loadError ? (
          <Text style={styles.error}>This photo could not be loaded.</Text>
        ) : (
          <ActivityIndicator color={colors.accent} />
        )}
        {showBefore && <Text style={styles.badge}>Before</Text>}
      </Pressable>

      <View style={styles.toolbar}>
        <Button label="Undo" disabled={!canUndo(state)} onPress={() => dispatch({ type: 'undo' })} />
        <Button label="Redo" disabled={!canRedo(state)} onPress={() => dispatch({ type: 'redo' })} />
        <Button label={compareOn ? 'After' : 'Before'} selected={compareOn} hint="Shows the original photo for comparison" onPress={() => setCompareOn((v) => !v)} />
        <Button label="Reset" onPress={() => dispatch({ type: 'reset' })} />
      </View>

      <View style={styles.tabs} accessibilityRole="tablist">
        {TABS.map((t) => (
          <Button key={t.id} label={t.label} variant="quiet" selected={tab === t.id} onPress={() => setTab(t.id)} style={styles.tab} />
        ))}
      </View>

      <ScrollView style={styles.panel} contentContainerStyle={styles.panelContent}>
        {tab === 'adjust' &&
          SLIDERS.map((s) => (
            <LabeledSlider key={s.key} label={s.label} min={s.min} max={s.max} value={state.candidate[s.key]} onChange={(v) => dispatch({ type: 'edit', patch: { [s.key]: v } })} />
          ))}
        {tab === 'looks' && (
          <>
            <View style={styles.wrap}>
              <Button label="None" selected={state.candidate.look === null} onPress={() => dispatch({ type: 'edit', patch: { look: null } })} />
              {LOOKS.map((l) => (
                <Button key={l.id} label={l.label} selected={state.candidate.look === l.id} onPress={() => dispatch({ type: 'edit', patch: { look: l.id } })} />
              ))}
            </View>
            {state.candidate.look !== null && (
              <LabeledSlider
                label={LOOK_INTENSITY.label}
                min={LOOK_INTENSITY.min}
                max={LOOK_INTENSITY.max}
                value={state.candidate.lookIntensity}
                onChange={(v) => dispatch({ type: 'edit', patch: { lookIntensity: v } })}
              />
            )}
          </>
        )}
        {tab === 'crop' && (
          <View style={styles.wrap}>
            {CROPS.map((c) => (
              <Button key={c.id} label={c.label} selected={state.candidate.crop === c.id} onPress={() => dispatch({ type: 'edit', patch: { crop: c.id } })} />
            ))}
          </View>
        )}
        {tab === 'ai' && (
          <View style={styles.list}>
            <Text style={styles.muted}>AI portrait effects need approved models and are not available in this build.</Text>
            {filters.map((f) => (
              <View key={f.id} style={styles.filterRow} accessible accessibilityLabel={`${f.display_name}, not available yet`}>
                <Text style={styles.body}>{f.display_name}</Text>
                <Text style={styles.caption}>Not available yet</Text>
              </View>
            ))}
          </View>
        )}
        {source.resizedFrom && (
          <Text style={styles.caption}>
            Resized from {source.resizedFrom.width}×{source.resizedFrom.height} to {source.width}×{source.height} to stay within 24 MP.
          </Text>
        )}
        {exportRect && !dirty && <Text style={styles.caption}>Export size: {exportRect.width}×{exportRect.height}</Text>}
        {exportState.kind === 'rendering' && <Text style={styles.caption} accessibilityLiveRegion="polite">Preparing full-size photo…</Text>}
        {exportState.kind === 'error' && <Text style={styles.error} accessibilityLiveRegion="assertive">{exportState.message}</Text>}
      </ScrollView>

      {dirty && (
        <View style={styles.commitBar}>
          <Button label="Discard" onPress={() => dispatch({ type: 'discard' })} style={styles.grow} />
          <Button label="Apply" variant="primary" onPress={() => dispatch({ type: 'apply' })} style={styles.grow} />
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.background },
  stage: { flex: 1, alignItems: 'center', justifyContent: 'center', margin: space(3) },
  badge: { position: 'absolute', top: space(2), left: space(2), ...type('caption'), color: colors.text, backgroundColor: colors.raised, paddingHorizontal: space(2), borderRadius: radii.small, overflow: 'hidden' },
  toolbar: { flexDirection: 'row', justifyContent: 'space-around', paddingHorizontal: space(3) },
  tabs: { flexDirection: 'row', paddingHorizontal: space(3), paddingTop: space(2) },
  tab: { flex: 1 },
  panel: { maxHeight: 260, backgroundColor: colors.surface, borderTopLeftRadius: radii.sheet, borderTopRightRadius: radii.sheet, marginTop: space(2) },
  panelContent: { padding: space(4), gap: space(2) },
  wrap: { flexDirection: 'row', flexWrap: 'wrap', gap: space(2) },
  list: { gap: space(2) },
  filterRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: space(1) },
  body: { ...type('body'), color: colors.text },
  muted: { ...type('body'), color: colors.muted },
  caption: { ...type('caption'), color: colors.muted },
  error: { ...type('body'), color: colors.error },
  commitBar: { flexDirection: 'row', gap: space(3), padding: space(3), backgroundColor: colors.surface },
  grow: { flex: 1 },
});
