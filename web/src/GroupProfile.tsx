import type { Group } from "./api";

type Props = { group: Group; searchedName: string };

export default function GroupProfile({ group, searchedName }: Props) {
  const otherNames = group.aliases.filter(
    (alias) => alias.name !== group.main_name,
  );
  const showMatch =
    searchedName.toLowerCase() !== group.main_name.toLowerCase();

  return (
    <article>
      {showMatch && (
        <p className="matched">
          MITRE lists “{searchedName}” as a name for
        </p>
      )}
      <h2>{group.main_name}</h2>

      {group.suspected_origin && (
        <p>Suspected origin: {group.suspected_origin}</p>
      )}

      <p className="summary">{group.summary || "No description available."}</p>

      <h3>Also known as</h3>
      {otherNames.length > 0 ? (
        <ul className="names">
          {otherNames.map((alias) => (
            <li key={`${alias.name}-${alias.source.url}`}>{alias.name}</li>
          ))}
        </ul>
      ) : (
        <p>No other names listed.</p>
      )}

      <details>
        <summary>Details for analysts</summary>
        {group.mitre_id && <p>MITRE ATT&amp;CK ID: {group.mitre_id}</p>}
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th scope="col">Name</th>
                <th scope="col">Vendor</th>
                <th scope="col">Relationship</th>
                <th scope="col">Confidence</th>
                <th scope="col">Source</th>
              </tr>
            </thead>
            <tbody>
              {group.aliases.map((alias) => (
                <tr key={`${alias.name}-${alias.source.url}`}>
                  <td>{alias.name}</td>
                  <td>{alias.vendor ?? "Not stated"}</td>
                  <td>{alias.relationship}</td>
                  <td>{alias.confidence}</td>
                  <td>
                    <a href={alias.source.url} target="_blank" rel="noreferrer">
                      MITRE
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>

      <p className="source">
        Source:{" "}
        <a href={group.source.url} target="_blank" rel="noreferrer">
          {group.source.title}
        </a>
      </p>
    </article>
  );
}
