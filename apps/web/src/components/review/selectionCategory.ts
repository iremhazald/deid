/** A first guess so a hearing label is not offered as a person name. */
export function suggestSelectionCategory(value: string): string {
  const text = value.trim();
  const compact = text.replace(/\s+/g, "");
  if (/@/.test(text) && text.includes(".")) return "EMAIL";
  if (/^TR\d{24}$/i.test(compact)) return "IBAN";
  if (/^\d{11}$/.test(compact)) return "NATIONAL_ID";
  if (/(?:\+90|0)\d{10}/.test(compact)) return "PHONE_NUMBER";
  if (/\d{1,2}[./]\d{1,2}[./]\d{2,4}/.test(text)) return "DATE";
  if (/mahkeme/i.test(text)) return "COURT_NAME";
  if (/\d{4}\s*\/\s*\d+/.test(text)) return "CASE_NUMBER";
  if (/(celse|esas|karar|dosya)\s*no/i.test(text)) return "FILE_NUMBER";
  return "PERSON_NAME";
}
