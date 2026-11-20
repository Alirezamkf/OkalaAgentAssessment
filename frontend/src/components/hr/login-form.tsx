"use client";

import { useRef, useState, type FormEvent } from "react";

type FieldErrors = { username?: string; password?: string };

export default function LoginForm() {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [serviceNotice, setServiceNotice] = useState(false);
  const usernameRef = useRef<HTMLInputElement>(null);
  const passwordRef = useRef<HTMLInputElement>(null);
  // Reserved for issue #204: only a real API request should activate this state.
  const isSubmitting = false;

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const nextErrors: FieldErrors = {};
    if (!username.trim()) nextErrors.username = "لطفاً نام کاربری خود را وارد کنید.";
    if (password.length === 0) nextErrors.password = "لطفاً رمز عبور خود را وارد کنید.";
    setErrors(nextErrors);
    setServiceNotice(false);

    if (nextErrors.username) {
      usernameRef.current?.focus();
      return;
    }
    if (nextErrors.password) {
      passwordRef.current?.focus();
      return;
    }

    // Integration point: issue #204 will call the existing auth service boundary
    // using the backend-approved contract. No authentication occurs here.
    setServiceNotice(true);
  }

  return (
    <form noValidate onSubmit={handleSubmit} aria-busy={isSubmitting}>
      <div className="mb-4">
        <label className="form-label" htmlFor="hr-username">نام کاربری <span className="hr-login-required">(الزامی)</span></label>
        <input
          ref={usernameRef}
          id="hr-username"
          name="username"
          type="text"
          className={`form-control${errors.username ? " is-invalid" : ""}`}
          autoComplete="username"
          autoCapitalize="none"
          spellCheck={false}
          required
          value={username}
          aria-invalid={Boolean(errors.username)}
          aria-describedby={`hr-username-hint${errors.username ? " hr-username-error" : ""}`}
          onChange={(event) => {
            setUsername(event.target.value);
            setErrors((current) => ({ ...current, username: undefined }));
            setServiceNotice(false);
          }}
        />
        <div id="hr-username-hint" className="form-text">نام کاربری سازمانی خود را وارد کنید.</div>
        {errors.username && <p id="hr-username-error" className="invalid-feedback" role="alert">{errors.username}</p>}
      </div>
      <div className="mb-4">
        <label className="form-label" htmlFor="hr-password">رمز عبور <span className="hr-login-required">(الزامی)</span></label>
        <div className="hr-login-password">
          <input
            ref={passwordRef}
            id="hr-password"
            name="password"
            type={showPassword ? "text" : "password"}
            className={`form-control${errors.password ? " is-invalid" : ""}`}
            autoComplete="current-password"
            required
            value={password}
            aria-invalid={Boolean(errors.password)}
            aria-describedby={errors.password ? "hr-password-error" : undefined}
            onChange={(event) => {
              setPassword(event.target.value);
              setErrors((current) => ({ ...current, password: undefined }));
              setServiceNotice(false);
            }}
          />
          <button type="button" className="hr-login-visibility" aria-controls="hr-password" aria-pressed={showPassword} aria-label={showPassword ? "پنهان کردن رمز عبور" : "نمایش رمز عبور"} onClick={() => setShowPassword((current) => !current)}>
            {showPassword ? "پنهان کردن" : "نمایش"}
          </button>
        </div>
        {errors.password && <p id="hr-password-error" className="invalid-feedback d-block" role="alert">{errors.password}</p>}
      </div>
      <div className="hr-login-notice" role="status" aria-live="polite" aria-atomic="true">
        {serviceNotice && <p>سرویس ورود هنوز به سامانه متصل نشده است. ورود انجام نشد؛ لطفاً پس از فعال شدن سرویس دوباره تلاش کنید.</p>}
      </div>
      <button className="btn hr-login-submit w-100" type="submit" disabled={isSubmitting}>
        {isSubmitting && <span className="spinner-border spinner-border-sm" aria-hidden="true" />}
        {isSubmitting ? "در حال بررسی…" : "ورود به سامانه"}
      </button>
    </form>
  );
}
