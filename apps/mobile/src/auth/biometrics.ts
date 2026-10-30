import * as LocalAuthentication from 'expo-local-authentication';

export interface Biometrics {
  isAvailable(): Promise<boolean>;
  authenticate(prompt: string, cancelLabel: string): Promise<boolean>;
}

export const deviceBiometrics: Biometrics = {
  async isAvailable() {
    const [hardware, enrolled] = await Promise.all([
      LocalAuthentication.hasHardwareAsync(),
      LocalAuthentication.isEnrolledAsync(),
    ]);
    return hardware && enrolled;
  },
  async authenticate(prompt, cancelLabel) {
    const result = await LocalAuthentication.authenticateAsync({
      promptMessage: prompt,
      cancelLabel,
      // Device passcode fallback keeps users who fail biometrics from being locked out.
      disableDeviceFallback: false,
    });
    return result.success;
  },
};
