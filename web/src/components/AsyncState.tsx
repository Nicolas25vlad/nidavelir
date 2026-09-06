type AsyncStateKind = "loading" | "empty" | "error";

type AsyncStateProps = {
  kind: AsyncStateKind;
  title: string;
  detail: string;
};

const toneByKind: Record<AsyncStateKind, string> = {
  loading: "muted",
  empty: "muted",
  error: "danger",
};

export function AsyncState({ kind, title, detail }: AsyncStateProps) {
  return (
    <div className={`state-panel state-panel--${toneByKind[kind]}`} role={kind === "error" ? "alert" : undefined}>
      <strong>{title}</strong>
      <span>{detail}</span>
    </div>
  );
}
