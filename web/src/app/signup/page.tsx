import { AuthShell } from "../_components/auth-shell";

export const metadata = {
  title: "Lookover Codex | Sign up",
  description: "Demo reviewer signup.",
};

export default async function SignupPage({
  searchParams,
}: {
  searchParams?: Promise<{ next?: string }>;
}) {
  const resolvedSearchParams = (await searchParams) ?? {};
  const nextPath =
    typeof resolvedSearchParams.next === "string" && resolvedSearchParams.next.startsWith("/")
      ? resolvedSearchParams.next
      : "/overview";
  return <AuthShell mode="signup" nextPath={nextPath} />;
}
