import type { Alias, Group, Vendor } from "./api";

function VendorLink({ vendor }: { vendor: Vendor }) {
  return (
    <a
      href={vendor.source.url}
      title={vendor.source.title}
      target="_blank"
      rel="noreferrer"
    >
      {vendor.name}
    </a>
  );
}

function VendorCell({ alias }: { alias: Alias }) {
  const vendors = alias.vendors ?? [];
  if (vendors.length > 0) {
    return vendors.map((vendor, index) => (
      <span key={`${vendor.name}-${vendor.source.url}`}>
        {index > 0 && ", "}
        <VendorLink vendor={vendor} />
      </span>
    ));
  }
  if (alias.likely_vendor) {
    return (
      <>
        Likely <VendorLink vendor={alias.likely_vendor} />
      </>
    );
  }
  return "Not stated";
}

function vendorNote(alias: Alias) {
  const vendors = alias.vendors ?? [];
  if (vendors.length > 0) {
    return vendors.map((vendor) => vendor.name).join(", ");
  }
  return alias.likely_vendor ? `likely ${alias.likely_vendor.name}` : "";
}

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
            <li key={`${alias.name}-${alias.source.url}`}>
              {alias.name}
              {vendorNote(alias) && (
                <span className="vendor"> {vendorNote(alias)}</span>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <p>No other names listed.</p>
      )}

      <details>
        <summary>Details for analysts</summary>
        {group.mitre_id && <p>MITRE ATT&amp;CK ID: {group.mitre_id}</p>}
        <p>
          Vendor is who created the name, according to MISP. “Likely” means no
          source states it, but the name fits that vendor’s public naming
          pattern.
        </p>
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
                  <td>
                    <VendorCell alias={alias} />
                  </td>
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
