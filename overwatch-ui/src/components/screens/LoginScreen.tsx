import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { GoogleLogin } from '@react-oauth/google';
import { authApi } from '@/lib/api';

export type UserRole = 'PRODUCER' | 'AUDITOR';
type AuthMode = 'LOGIN' | 'SIGNUP';

interface LoginScreenProps {
  initialMode: AuthMode;
  onLogin: (name: string, role: UserRole) => void | Promise<void>;
  onBack?: () => void;
}

export default function LoginScreen({ initialMode, onLogin, onBack }: LoginScreenProps) {
  const [role, setRole] = useState<UserRole>('PRODUCER');
  const [mode, setMode] = useState<AuthMode>(initialMode);
  
  const [email, setEmail] = useState('');
  const [name, setName] = useState('');
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    setMode(initialMode);
    setError('');
  }, [initialMode]);

  const googleClientId = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined;

  const handleDirectLogin = async (e?: React.FormEvent, directRole?: UserRole, directEmail?: string, directName?: string) => {
    if (e) e.preventDefault();
    const targetRole = directRole || role;
    const targetEmail = (directEmail || email || (targetRole === 'PRODUCER' ? 'feeder@overwatch.ai' : 'auditor@overwatch.ai')).trim();
    const targetName = (directName || name || (targetRole === 'PRODUCER' ? 'Data Feeder' : 'Lead Auditor')).trim();

    setLoading(true);
    setError('');
    try {
      const result = await authApi.directAuth(targetEmail, targetName, targetRole);
      if (!result.ok) {
        setError(result.error || 'Authentication failed. Please try again.');
        return;
      }
      await onLogin(result.data.name, result.data.role as UserRole);
    } catch (err: any) {
      setError(err?.message || 'Failed to authenticate');
    } finally {
      setLoading(false);
    }
  };

  const handleGoogleSuccess = async (credential?: string) => {
    if (!credential) {
      setError('Google sign-in did not return a token. Please try again.');
      return;
    }
    setGoogleLoading(true);
    setError('');
    try {
      const result = await authApi.googleAuth(credential, mode, role);
      if (!result.ok) {
        setError(result.error || 'Google sign-in failed.');
        return;
      }
      await onLogin(result.data.name, result.data.role as UserRole);
    } catch (err: any) {
      setError(err?.message || 'Google authentication failed.');
    } finally {
      setGoogleLoading(false);
    }
  };

  return (
    <div 
      className="min-h-screen w-full flex items-center justify-center relative bg-[#F9FAFB] font-sans px-4 py-8"
    >
      {onBack && (
        <button
          onClick={onBack}
          className="absolute top-8 left-8 text-gray-500 hover:text-gray-900 text-sm font-medium flex items-center gap-2 transition-colors z-20 cursor-pointer"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M19 12H5M12 19l-7-7 7-7"/></svg>
          Back
        </button>
      )}

      <motion.div 
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, ease: 'easeOut' }}
        className="w-full max-w-[440px] p-8 md:p-10 bg-white rounded-2xl border border-gray-100 shadow-[0_8px_30px_rgb(0,0,0,0.04)] relative z-10"
      >
        <div className="mb-6">
          <div className="w-10 h-10 rounded-lg bg-gray-900 mb-5 flex items-center justify-center shadow-sm">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#ffffff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
            </svg>
          </div>
          <h1 className="text-2xl font-semibold text-gray-900 tracking-tight mb-1.5">
            {mode === 'LOGIN' ? 'Sign in to Overwatch' : 'Create an account'}
          </h1>
          <p className="text-sm text-gray-500">
            Forensic media intelligence command center
          </p>
        </div>

        {/* Role Selector */}
        <div className="flex p-1 rounded-lg mb-6 bg-gray-100/80 border border-gray-200/50">
          {(['PRODUCER', 'AUDITOR'] as const).map((r) => (
            <button 
              key={r} 
              type="button" 
              onClick={() => setRole(r)} 
              className={`flex-1 py-2 text-sm font-medium rounded-md relative z-10 transition-colors cursor-pointer ${role === r ? 'text-gray-900' : 'text-gray-500 hover:text-gray-700'}`}
            >
              {r === 'PRODUCER' ? 'Data Feeder' : 'Auditor'}
              {role === r && (
                <motion.div 
                  layoutId="role-pill" 
                  className="absolute inset-0 rounded-md bg-white shadow-sm border border-gray-200/50 -z-10" 
                  transition={{ type: 'spring', stiffness: 500, damping: 35 }} 
                />
              )}
            </button>
          ))}
        </div>

        {/* Quick Demo Access Buttons */}
        <div className="mb-6 p-4 rounded-xl bg-gray-50 border border-gray-200/60">
          <p className="text-[11px] font-semibold text-gray-700 uppercase tracking-wider mb-2.5 flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            Instant Demo Access
          </p>
          <div className="grid grid-cols-2 gap-2.5">
            <button
              type="button"
              disabled={loading}
              onClick={() => handleDirectLogin(undefined, 'PRODUCER', 'feeder@overwatch.ai', 'Feeder Operator')}
              className="px-3 py-2 text-xs font-semibold rounded-lg bg-white border border-gray-200 hover:border-gray-900 hover:bg-gray-900 hover:text-white transition-all text-gray-800 shadow-sm text-center cursor-pointer disabled:opacity-50"
            >
              Demo as Feeder
            </button>
            <button
              type="button"
              disabled={loading}
              onClick={() => handleDirectLogin(undefined, 'AUDITOR', 'auditor@overwatch.ai', 'Lead Auditor')}
              className="px-3 py-2 text-xs font-semibold rounded-lg bg-white border border-gray-200 hover:border-gray-900 hover:bg-gray-900 hover:text-white transition-all text-gray-800 shadow-sm text-center cursor-pointer disabled:opacity-50"
            >
              Demo as Auditor
            </button>
          </div>
        </div>

        <div className="relative flex items-center justify-center my-5">
          <div className="border-t border-gray-200 w-full"></div>
          <span className="bg-white px-3 text-xs text-gray-400 font-medium uppercase tracking-wider">or sign in with email</span>
        </div>

        {/* Direct Email Form */}
        <form onSubmit={(e) => handleDirectLogin(e)} className="space-y-3.5 mb-5">
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Operator Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder={role === 'PRODUCER' ? 'feeder@example.com' : 'auditor@example.com'}
              className="w-full px-3.5 py-2.5 text-sm rounded-lg border border-gray-200 focus:outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent transition-all bg-white"
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">
              Display Name
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Tanmay Kumar"
              className="w-full px-3.5 py-2.5 text-sm rounded-lg border border-gray-200 focus:outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent transition-all bg-white"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 px-4 rounded-lg bg-gray-900 hover:bg-black text-white text-sm font-semibold transition-all shadow-sm cursor-pointer disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {loading ? (
              <>
                <svg className="animate-spin h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Authenticating...
              </>
            ) : (
              `Enter as ${role === 'PRODUCER' ? 'Data Feeder' : 'Auditor'}`
            )}
          </button>
        </form>

        {/* Google OAuth (Optional) */}
        {googleClientId && (
          <div className="pt-2">
            <div className="w-full flex justify-center [&>div]:w-full">
              <GoogleLogin
                onSuccess={(credentialResponse) => {
                  void handleGoogleSuccess(credentialResponse.credential);
                }}
                onError={() => setError('Google sign-in blocked by browser or failed. Use Instant Demo Access above.')}
                text={mode === 'SIGNUP' ? 'signup_with' : 'signin_with'}
                width="100%"
                shape="rectangular"
                size="large"
                logo_alignment="center"
              />
            </div>
            {googleLoading && (
              <p className="text-xs text-gray-500 text-center flex items-center justify-center gap-2 mt-2">
                <svg className="animate-spin h-3 w-3 text-gray-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                Authenticating with Google...
              </p>
            )}
          </div>
        )}

        {/* Error Notification */}
        {error && (
          <div className="mt-4 p-3 bg-red-50 text-red-700 rounded-lg text-xs border border-red-100 flex items-start gap-2">
            <svg className="w-4 h-4 mt-0.5 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
            <span>{error}</span>
          </div>
        )}

        <div className="mt-6 pt-4 border-t border-gray-100">
          <p className="text-[11px] text-center text-gray-400">
            Demo and authorized sessions are protected by AES-256 JWT tokens.
          </p>
        </div>
      </motion.div>
    </div>
  );
}
