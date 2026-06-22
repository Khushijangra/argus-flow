"use client";

import { ChangeEvent, useEffect, useMemo, useState } from "react";

type Profile = {
  key: string;
  label: string;
  dataset_name: string;
  headline: string;
  note: string;
  badge: string;
  accent: string;
  benchmark_micro_auc: number;
  benchmark_macro_auc: number;
  benchmark_clip_auc: number;
  benchmark_micro_auc_pct: string;
  benchmark_macro_auc_pct: string;
  benchmark_clip_auc_pct: string;
  benchmark_report: string;
};

type AnalysisFrame = {
  index: number;
  timestamp_sec: number;
  score: number;
  caption: string;
  image_data_url: string;
};

type AnalysisResponse = {
  profile: Profile;
  analysis: {
    video_name: string;
    cache_hit: boolean;
    runtime_sec: number;
    timeline: {
      timestamps_sec: number[];
      scores: number[];
      threshold: number;
      threshold_label: string;
      anomaly_regions: Array<{
        start_time_sec: number;
        end_time_sec: number;
        start_index: number;
        end_index: number;
      }>;
    };
    summary: {
      duration_sec: number;
      peak_time_sec: number;
      peak_score: number;
      raw_frame_count: number;
      sampled_frame_count: number;
      sample_step: number;
      source_fps: number;
      clip_count: number;
      profile_label: string;
      profile_dataset: string;
    };
    frames: AnalysisFrame[];
  };
  request?: {
    profile: string;
    filename: string;
  };
};

const API_BASE = (process.env.NEXT_PUBLIC_ARGUS_API_URL ?? "").replace(/\/$/, "");

function pct(value: number): string {
  return `${(value * 100).toFixed(2)}%`;
}

function sec(value: number): string {
  return `${value.toFixed(2)}s`;
}

function TimelineChart({
  timeline,
  accent,
}: {
  timeline: AnalysisResponse["analysis"]["timeline"] | null;
  accent: string;
}) {
  const width = 920;
  const height = 320;
  const padding = { top: 20, right: 20, bottom: 42, left: 54 };

  const chart = useMemo(() => {
    if (!timeline || timeline.timestamps_sec.length === 0 || timeline.scores.length === 0) {
      return null;
    }

    const plotWidth = width - padding.left - padding.right;
    const plotHeight = height - padding.top - padding.bottom;
    const maxX = Math.max(...timeline.timestamps_sec, 1);
    const maxY = Math.max(...timeline.scores, timeline.threshold, 1);

    const x = (value: number) => padding.left + (value / maxX) * plotWidth;
    const y = (value: number) =>
      padding.top + plotHeight - (value / maxY) * plotHeight;

    const linePath = timeline.timestamps_sec
      .map((time, index) => `${index === 0 ? "M" : "L"} ${x(time).toFixed(2)} ${y(timeline.scores[index]).toFixed(2)}`)
      .join(" ");

    const areaPath = `${linePath} L ${x(
      timeline.timestamps_sec[timeline.timestamps_sec.length - 1]
    ).toFixed(2)} ${(padding.top + plotHeight).toFixed(2)} L ${x(
      timeline.timestamps_sec[0]
    ).toFixed(2)} ${(padding.top + plotHeight).toFixed(2)} Z`;

    return {
      maxX,
      maxY,
      x,
      y,
      linePath,
      areaPath,
    };
  }, [timeline]);

  if (!chart) {
    return (
      <div className="chart-empty">
        Upload a video and run analysis to generate the anomaly timeline.
      </div>
    );
  }

  const data = timeline!;
  const { x, y, areaPath, linePath, maxX, maxY } = chart;
  const yTicks = [0, 0.25, 0.5, 0.75, 1].map((v) => Math.min(v, maxY));
  const xTicks = Array.from({ length: 6 }, (_, idx) => (maxX / 5) * idx);

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="timeline-svg" role="img" aria-label="Anomaly timeline">
      <defs>
        <linearGradient id="timeline-fill" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor={accent} stopOpacity="0.32" />
          <stop offset="100%" stopColor={accent} stopOpacity="0.06" />
        </linearGradient>
      </defs>

      <rect x="0" y="0" width={width} height={height} rx="20" className="timeline-bg" />

      {data.anomaly_regions.map((region, idx) => (
        <rect
          key={`${region.start_time_sec}-${region.end_time_sec}-${idx}`}
          x={x(region.start_time_sec)}
          y={padding.top}
          width={Math.max(6, x(region.end_time_sec) - x(region.start_time_sec))}
          height={height - padding.top - padding.bottom}
          className="timeline-region"
        />
      ))}

      {yTicks.map((tick) => (
        <g key={`y-${tick}`}>
          <line
            x1={padding.left}
            x2={width - padding.right}
            y1={y(tick)}
            y2={y(tick)}
            className="grid-line"
          />
          <text x={padding.left - 12} y={y(tick) + 4} className="axis-text axis-text-right">
            {tick.toFixed(2)}
          </text>
        </g>
      ))}

      {xTicks.map((tick) => (
        <g key={`x-${tick}`}>
          <line
            x1={x(tick)}
            x2={x(tick)}
            y1={padding.top}
            y2={height - padding.bottom}
            className="grid-line grid-line-vertical"
          />
          <text x={x(tick)} y={height - 14} className="axis-text axis-text-center">
            {tick.toFixed(1)}s
          </text>
        </g>
      ))}

      <line
        x1={padding.left}
        x2={width - padding.right}
        y1={y(data.threshold)}
        y2={y(data.threshold)}
        className="threshold-line"
      />
      <text x={padding.left + 8} y={y(data.threshold) - 8} className="threshold-text">
        {data.threshold_label}
      </text>

      <path d={areaPath} fill="url(#timeline-fill)" />
      <path d={linePath} fill="none" stroke={accent} strokeWidth="4" strokeLinecap="round" />
    </svg>
  );
}

export default function Page() {
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [selectedKey, setSelectedKey] = useState<string>("");
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string>("");
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>("");
  const [apiReady, setApiReady] = useState(false);

  useEffect(() => {
    if (!API_BASE) {
      setError("Set NEXT_PUBLIC_ARGUS_API_URL before deploying the Vercel frontend.");
      return;
    }

    const controller = new AbortController();
    fetch(`${API_BASE}/profiles`, { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`Failed to load profiles (${response.status})`);
        }
        return (await response.json()) as { profiles: Profile[] };
      })
      .then((payload) => {
        setProfiles(payload.profiles);
        if (payload.profiles.length > 0) {
          setSelectedKey(payload.profiles[0].key);
        }
        setApiReady(true);
        setError("");
      })
      .catch((err: Error) => {
        if (err.name !== "AbortError") {
          setError(err.message);
        }
      });

    return () => controller.abort();
  }, []);

  const selectedProfile = useMemo(
    () => profiles.find((profile) => profile.key === selectedKey) ?? null,
    [profiles, selectedKey]
  );

  function onVideoChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] ?? null;
    setVideoFile(file);
    setAnalysis(null);
    setError("");

    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
      setPreviewUrl("");
    }

    if (file) {
      setPreviewUrl(URL.createObjectURL(file));
    }
  }

  async function analyzeVideo() {
    if (!API_BASE || !selectedProfile || !videoFile) {
      return;
    }

    setLoading(true);
    setError("");
    setAnalysis(null);

    const formData = new FormData();
    formData.append("profile", selectedProfile.label);
    formData.append("video", videoFile);

    try {
      const response = await fetch(`${API_BASE}/analyze`, {
        method: "POST",
        body: formData,
      });

      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.detail || `Analysis failed (${response.status})`);
      }

      setAnalysis(payload as AnalysisResponse);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown analysis failure.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="page-shell">
      <section className="hero">
        <div className="hero-kicker">Vercel + Modal deployment</div>
        <h1>ARGUS Stream A</h1>
        <p>
          Frame-level video anomaly detection with a Vercel frontend and a Modal FastAPI backend.
          Upload a short clip, choose Avenue or UBnormal, and inspect the live anomaly timeline.
        </p>
        <div className="chip-row">
          <span>Modal FastAPI</span>
          <span>Vercel frontend</span>
        </div>
      </section>

      <section className="layout-grid">
        <div className="card input-card">
          <div className="section-kicker">Input</div>
          <h2>Upload video and choose profile</h2>
          <p className="muted">
            Use the same uploaded clip to compare the saved Avenue and UBnormal profiles.
          </p>

          <label className="field-label">Analysis profile</label>
          <div className="profile-toggle">
            {profiles.map((profile) => (
              <button
                key={profile.key}
                type="button"
                className={`profile-pill ${selectedKey === profile.key ? "active" : ""}`}
                onClick={() => setSelectedKey(profile.key)}
              >
                {profile.dataset_name}
              </button>
            ))}
          </div>

          <label className="field-label" htmlFor="video-upload">
            Video file
          </label>
          <input id="video-upload" type="file" accept="video/*" onChange={onVideoChange} />

          {previewUrl ? (
            <video className="video-preview" src={previewUrl} controls playsInline />
          ) : (
            <div className="video-placeholder">Choose a short video clip to preview it here.</div>
          )}

          <button
            type="button"
            className="analyze-button"
            disabled={!apiReady || !selectedProfile || !videoFile || loading}
            onClick={analyzeVideo}
          >
            {loading ? "Analyzing..." : "Run live analysis"}
          </button>

          {error ? <div className="error-banner">{error}</div> : null}
        </div>

        <div className="card profile-card">
          <div className="section-kicker">Saved profile metrics</div>
          <h2>{selectedProfile ? selectedProfile.dataset_name : "Loading profile"}</h2>
          <p className="muted">
            {selectedProfile
              ? selectedProfile.note
              : "Loading saved metrics from the backend."}
          </p>

          {selectedProfile ? (
            <>
              <div className="metric-grid">
                <div className="metric-tile">
                  <div className="metric-label">Saved micro AUC</div>
                  <div className="metric-value">{selectedProfile.benchmark_micro_auc_pct}</div>
                </div>
                <div className="metric-tile">
                  <div className="metric-label">Saved macro AUC</div>
                  <div className="metric-value">{selectedProfile.benchmark_macro_auc_pct}</div>
                </div>
              </div>
              <div className="profile-note">
                <strong>{selectedProfile.headline}</strong>
                <span>{selectedProfile.badge}</span>
              </div>
            </>
          ) : null}
        </div>
      </section>

      <section className="card chart-card">
        <div className="section-kicker">Live result</div>
        <h2>Anomaly timeline</h2>
        <p className="muted">
          Timeline generated from the uploaded video under the selected saved profile.
        </p>
        <TimelineChart
          timeline={analysis?.analysis.timeline ?? null}
          accent={analysis?.profile.accent ?? "#0ea5e9"}
        />
      </section>

      <section className="results-grid">
        <div className="card summary-card">
          <div className="section-kicker">Analysis summary</div>
          <h2>Live analysis summary</h2>
          <p className="muted">
            {analysis
              ? `Uploaded video analyzed under the ${analysis.profile.dataset_name} saved profile.`
              : "Run an analysis to populate runtime, peak anomaly, and clip coverage."}
          </p>

          {analysis ? (
            <div className="summary-grid">
              <div className="summary-tile">
                <div className="metric-label">Profile</div>
                <div className="metric-value-small">{analysis.profile.dataset_name}</div>
              </div>
              <div className="summary-tile">
                <div className="metric-label">Clip duration</div>
                <div className="metric-value-small">{sec(analysis.analysis.summary.duration_sec)}</div>
              </div>
              <div className="summary-tile">
                <div className="metric-label">Peak anomaly</div>
                <div className="metric-value-small">{sec(analysis.analysis.summary.peak_time_sec)}</div>
              </div>
              <div className="summary-tile">
                <div className="metric-label">Runtime</div>
                <div className="metric-value-small">{sec(analysis.analysis.runtime_sec)}</div>
              </div>
              <div className="summary-tile">
                <div className="metric-label">Frames analyzed</div>
                <div className="metric-value-small">
                  {analysis.analysis.summary.sampled_frame_count} / {analysis.analysis.summary.raw_frame_count}
                </div>
              </div>
              <div className="summary-tile">
                <div className="metric-label">Clip embeddings</div>
                <div className="metric-value-small">{analysis.analysis.summary.clip_count}</div>
              </div>
            </div>
          ) : null}
        </div>

        <div className="card gallery-card">
          <div className="section-kicker">Frame evidence</div>
          <h2>Highest-scoring frames</h2>
          <p className="muted">
            Top anomalous moments extracted from the uploaded clip.
          </p>
          <div className="frame-grid">
            {analysis?.analysis.frames.length ? (
              analysis.analysis.frames.map((frame) => (
                <figure className="frame-item" key={`${frame.index}-${frame.timestamp_sec}`}>
                  <img src={frame.image_data_url} alt={frame.caption} />
                  <figcaption>{frame.caption}</figcaption>
                </figure>
              ))
            ) : (
              <div className="empty-gallery">Run an analysis to see top-scoring frames.</div>
            )}
          </div>
        </div>
      </section>
    </main>
  );
}
