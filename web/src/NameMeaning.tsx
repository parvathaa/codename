import type { Reading } from "./api";

type Props = { name: string; readings: Reading[] };

export default function NameMeaning({ name, readings }: Props) {
  if (readings.length === 0) return null;

  return (
    <div className="meaning">
      <h2>What “{name}” may tell you</h2>
      <ul>
        {readings.map((reading) => (
          <li key={`${reading.vendor}-${reading.clue}`}>
            If this is a <strong>{reading.vendor}</strong> name, “{reading.clue}”
            means <strong>{reading.meaning}</strong>.{" "}
            <a href={reading.source.url} target="_blank" rel="noreferrer">
              {reading.source.title}
            </a>
          </li>
        ))}
      </ul>
      <p>
        This explains the name only. It doesn’t prove who is behind an attack,
        and other companies may use the same word.
      </p>
    </div>
  );
}
