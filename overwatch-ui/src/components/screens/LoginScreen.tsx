import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { GoogleLogin } from '@react-oauth/google';
import { authApi } from '@/lib/api';

export type UserRole = 'PRODUCER' | 'AUDITOR';
type AuthMode = 'LOGIN' | 'SIGNUP';
type AuthStep = 'EMAIL' | 'OTP';

interface LoginScreenProps {
  initialMode: AuthMode;
  onLogin: (name: string, role: UserRole) => void | Promise<void>;
  onBack?: () => void;
}

export default function LoginScreen({ initialMode, onLogin, onBack }: LoginScreenProps) {
  const [role, setRole] = useState<UserRole>('PRODUCER');
  const [mode, setMode] = useState<AuthMode>(initialMode);
  const [step, setStep] = useState<AuthStep>('EMAIL');
  
  const [email, setEmail] = useState('');
  const [name, setName] = useState('');
  const [code, setCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    setMode(initialMode);
    setStep('EMAIL');
    setError('');
  }, [initialMode]);

  const googleClientId = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined;

  const isSubmitting = React.useRef(false);

  // Step 1: Send the email to FastAPI to generate the code
  const handleRequestOTP = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || isSubmitting.current) return;
    if (mode === 'SIGNUP' && !name.trim()) {
      setError('Please enter your name to create an account.');
      return;
    }
    
    isSubmitting.current = true;
    setLoading(true);
    setError('');
    
    // Pass the name ONLY if they are signing up
    const result = await authApi.requestOtp(
      email,
      role,
      mode,
      mode === 'SIGNUP' ? name : undefined,
    );
    
    if (!result.ok) {
      setError(result.error || 'Failed to send code. Please try again.');
    } else {
      setStep('OTP');
    }
    
    setLoading(false);
    isSubmitting.current = false;
  };

  // Step 2: Send the 6-digit code to FastAPI to get the JWT
  const handleVerifyOTP = async (e: React.FormEvent) => {
    e.preventDefault();
    if (code.length !== 6 || isSubmitting.current) {
      if (code.length !== 6) setError('Please enter the 6-digit code.');
      return;
    }
    
    isSubmitting.current = true;
    setLoading(true);
    setError('');
    
    const result = await authApi.verifyOtp(email, code);
    
    if (!result.ok) {
      setError(result.error || 'Invalid or expired code.');
      setLoading(false);
      isSubmitting.current = false;
    } else {
      // Success! The API client saved the JWT. Now trigger the UI handoff.
      await onLogin(result.data.name, result.data.role as UserRole);
      // We don't reset isSubmitting here because we're navigating away
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
    } finally {
      setGoogleLoading(false);
    }
  };

  return (
    <div 
      className="min-h-screen w-full flex items-center justify-center relative overflow-hidden font-['DM_Sans',sans-serif]" 
      style={{ background: 'transparent' }}
    >
      {onBack && (
        <button
          onClick={onBack}
          className="absolute top-8 left-10 text-[#6B6860] hover:text-[#0F0F0F] font-semibold flex items-center gap-2 transition-colors z-20"
        >
          &larr; Back
        </button>
      )}

      <div 
        className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[700px] h-[700px] blur-[120px] rounded-full pointer-events-none" 
        style={{ background: 'radial-gradient(circle, #4C63F715, transparent 65%)' }}
      />

      <motion.div 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ type: 'spring', damping: 25, stiffness: 300 }}
        className="w-full max-w-[460px] p-10 rounded-[28px] relative z-10"
        style={{ background: '#FFFFFF', border: '1px solid rgba(0,0,0,0.06)', boxShadow: '0 12px 40px rgba(0,0,0,0.06)' }}
      >
        <div className="text-center mb-8">
          <div className="w-12 h-12 rounded-xl mx-auto mb-5 flex items-center justify-center" style={{ background: 'linear-gradient(135deg, #4C63F7, #7C5CF7)', boxShadow: '0 6px 16px rgba(76, 99, 247, 0.25)' }}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
          </div>
          <h1 className="text-3xl font-bold text-[#0F0F0F] tracking-tight mb-2">
            {step === 'EMAIL' 
              ? (mode === 'LOGIN' ? 'Log in to Overwatch' : 'Create an account')
              : 'Enter verification code'}
          </h1>
          <p className="text-[15px] text-[#6B6860]">
            {step === 'EMAIL' 
              ? 'Join the intelligence network.' 
              : `We sent a 6-digit code to ${email}`}
          </p>
        </div>

        <AnimatePresence mode="wait">
          {step === 'EMAIL' ? (
            <motion.div key="email-step" initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 20 }}>
              
              <div className="flex p-1 rounded-xl mb-8 relative" style={{ background: '#EEEBE3', border: '1px solid rgba(0,0,0,0.04)' }}>
                {(['PRODUCER', 'AUDITOR'] as const).map((r) => (
                  <button key={r} type="button" onClick={() => setRole(r)} className={`flex-1 py-2.5 text-[14px] font-bold rounded-lg relative z-10 transition-colors ${role === r ? 'text-[#0F0F0F]' : 'text-[#6B6860] hover:text-[#0F0F0F]'}`}>
                    {r === 'PRODUCER' ? 'Data Feeder' : 'Auditor'}
                    {role === r && <motion.div layoutId="role-pill" className="absolute inset-0 rounded-lg -z-10" style={{ background: '#FFFFFF', boxShadow: '0 2px 8px rgba(0,0,0,0.06)' }} transition={{ type: 'spring', stiffness: 400, damping: 30 }} />}
                  </button>
                ))}
              </div>

              <form className="space-y-4" onSubmit={handleRequestOTP}>
                {googleClientId && (
                  <div className="mb-4">
                    <GoogleLogin
                      onSuccess={(credentialResponse) => {
                        void handleGoogleSuccess(credentialResponse.credential);
                      }}
                      onError={() => setError('Google sign-in failed. Please try email instead.')}
                      text={mode === 'SIGNUP' ? 'signup_with' : 'signin_with'}
                      width="100%"
                      shape="pill"
                    />
                    {googleLoading && (
                      <p className="mt-2 text-xs text-[#6B6860] text-center">Signing in with Google...</p>
                    )}
                  </div>
                )}

                {googleClientId && (
                  <div className="flex items-center gap-3 my-1">
                    <div className="h-px bg-black/10 flex-1" />
                    <span className="text-[11px] tracking-[0.12em] text-[#6B6860] uppercase">or</span>
                    <div className="h-px bg-black/10 flex-1" />
                  </div>
                )}

                {/* Conditionally render Name input for SIGNUP mode */}
                {mode === 'SIGNUP' && (
                  <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }}>
                    <input 
                      type="text" 
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="Full Name" 
                      required={mode === 'SIGNUP'}
                      className="w-full rounded-xl px-4 py-3.5 text-[15px] font-medium outline-none mb-4"
                      style={{ background: '#FFFFFF', border: '1.5px solid rgba(0,0,0,0.08)', color: '#0F0F0F' }}
                      onFocus={e => e.currentTarget.style.borderColor = '#4C63F7'}
                      onBlur={e => e.currentTarget.style.borderColor = 'rgba(0,0,0,0.08)'}
                    />
                  </motion.div>
                )}

                <input 
                  type="email" 
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="Email address" 
                  required
                  className="w-full rounded-xl px-4 py-3.5 text-[15px] font-medium outline-none"
                  style={{ background: '#FFFFFF', border: '1.5px solid rgba(0,0,0,0.08)', color: '#0F0F0F' }}
                  onFocus={e => e.currentTarget.style.borderColor = '#4C63F7'}
                  onBlur={e => e.currentTarget.style.borderColor = 'rgba(0,0,0,0.08)'}
                />
                
                {error && <p className="text-red-500 text-sm font-medium">{error}</p>}

                <button 
                  type="submit"
                  disabled={loading}
                  className="w-full py-3.5 px-4 rounded-xl text-[15px] font-bold text-white transition-all active:scale-[0.98] disabled:opacity-70 disabled:cursor-not-allowed"
                  style={{ background: 'linear-gradient(135deg, #4C63F7, #7C5CF7)', boxShadow: '0 6px 20px rgba(76, 99, 247, 0.3)' }}
                >
                  {loading ? 'Sending...' : 'Continue with Email'}
                </button>
              </form>
            </motion.div>
          ) : (
            <motion.div key="otp-step" initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 20 }}>
              <form className="space-y-4" onSubmit={handleVerifyOTP}>
                <input 
                  type="text" 
                  maxLength={6}
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
                  placeholder="000000" 
                  autoFocus
                  className="w-full rounded-xl px-4 py-4 text-center text-3xl tracking-[1em] font-mono outline-none"
                  style={{ background: '#FFFFFF', border: '1.5px solid rgba(0,0,0,0.08)', color: '#0F0F0F' }}
                  onFocus={e => e.currentTarget.style.borderColor = '#4C63F7'}
                  onBlur={e => e.currentTarget.style.borderColor = 'rgba(0,0,0,0.08)'}
                />
                
                {error && <p className="text-red-500 text-sm font-medium text-center">{error}</p>}

                <button 
                  type="submit"
                  disabled={loading || code.length !== 6}
                  className="w-full py-3.5 px-4 rounded-xl text-[15px] font-bold text-white transition-all active:scale-[0.98] disabled:opacity-70 disabled:cursor-not-allowed"
                  style={{ background: 'linear-gradient(135deg, #4C63F7, #7C5CF7)', boxShadow: '0 6px 20px rgba(76, 99, 247, 0.3)' }}
                >
                  {loading ? 'Verifying...' : 'Verify Code'}
                </button>
                
                <button type="button" onClick={() => setStep('EMAIL')} className="w-full text-[13px] font-medium text-[#6B6860] hover:text-[#0F0F0F] mt-2">
                  Use a different email
                </button>
              </form>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    </div>
  );
}