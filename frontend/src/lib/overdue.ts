// Calculo de atraso no cliente, espelhando o backend (RF30, DT11). Atualiza por
// temporizador e ao voltar para a aba, sem gravacoes periodicas.

export function isDateOverdue(dateStr: string, tz: string, now = new Date()): boolean {
  if (!dateStr) return false;
  const [y, m, d] = dateStr.split("-").map(Number);
  if (!y || !m || !d) return false;
  // Inicio do dia seguinte no fuso do kanban.
  const nextDay = new Date(Date.UTC(y, m - 1, d + 1, 0, 0, 0));
  const dueLocalMs = instantForLocalMidnight(nextDay, tz);
  return now.getTime() >= dueLocalMs;
}

export function isDateTimeOverdue(iso: string, now = new Date()): boolean {
  if (!iso) return false;
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return false;
  return now.getTime() > t;
}

// Converte uma data "parede" (meia-noite) no fuso informado para epoch ms.
function instantForLocalMidnight(utcMidnight: Date, tz: string): number {
  // Descobre o offset do fuso para aquela data usando Intl.
  const fmt = new Intl.DateTimeFormat("en-US", {
    timeZone: tz,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
  // Estima o offset aplicando o formatador ao instante UTC.
  const parts = fmt.formatToParts(utcMidnight);
  const map: Record<string, number> = {};
  for (const p of parts) if (p.type !== "literal") map[p.type] = Number(p.value);
  const asUtc = Date.UTC(
    map.year,
    map.month - 1,
    map.day,
    map.hour % 24,
    map.minute,
    map.second,
  );
  const offset = asUtc - utcMidnight.getTime();
  return utcMidnight.getTime() - offset;
}
