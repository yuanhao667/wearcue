export function GenderIcon({ gender }: { gender: "mens" | "womens" }) {
  return gender === "mens" ? (
    <svg className="login-gender-icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="4" r="2.6" /><path d="M7.2 8.2h9.6l2.1 6.2-2.4.8-1.4-4v10h-2.3v-6.5h-1.6v6.5H8.9v-10l-1.4 4-2.4-.8 2.1-6.2Z" /></svg>
  ) : (
    <svg className="login-gender-icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="4" r="2.6" /><path d="M8.1 8.2h7.8l3.2 7.6h-3.5v5.4h-2.3v-5.4h-2.6v5.4H8.4v-5.4H4.9l3.2-7.6Z" /></svg>
  );
}
