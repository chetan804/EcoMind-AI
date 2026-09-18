import { useEffect, useState } from 'react'
import { Link } from 'expo-router'
import { ActivityIndicator, Pressable, SafeAreaView, StyleSheet, Text, View } from 'react-native'
import { api } from '../src/api'

type Profile = { name: string; role_id: number }
type Report = { id: number; description: string; status: string }

export default function HomeScreen() {
  const [profile, setProfile] = useState<Profile | null>(null)
  const [reports, setReports] = useState<Report[]>([])
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([api<Profile>('/users/me'), api<Report[]>('/waste-reports/my-reports')])
      .then(([currentProfile, currentReports]) => { setProfile(currentProfile); setReports(currentReports) })
      .catch((requestError: Error) => setError(requestError.message))
  }, [])

  return <SafeAreaView style={styles.screen}><Text style={styles.eyebrow}>EcoMind AI</Text><Text style={styles.title}>Cleaner work, visible impact.</Text>{error ? <Text style={styles.error}>{error}</Text> : !profile ? <ActivityIndicator color="#1f6b4d" /> : <><Text style={styles.greeting}>Welcome, {profile.name}</Text><View style={styles.panel}><Text style={styles.panelTitle}>My reports</Text>{reports.length === 0 ? <Text style={styles.muted}>No reports yet.</Text> : reports.slice(0, 5).map((report) => <View key={report.id} style={styles.row}><Text style={styles.rowText}>{report.description}</Text><Text style={styles.status}>{report.status}</Text></View>)}</View><Link href="/report" asChild><Pressable style={styles.button}><Text style={styles.buttonText}>Report waste</Text></Pressable></Link></>}</SafeAreaView>
}

const styles = StyleSheet.create({
  screen: { flex: 1, padding: 24, backgroundColor: '#f5f7f3' },
  eyebrow: { color: '#1f6b4d', fontWeight: '700', letterSpacing: 2, textTransform: 'uppercase' },
  title: { color: '#17221d', fontSize: 32, fontWeight: '700', marginVertical: 16 },
  greeting: { color: '#6d7a72', marginBottom: 18 },
  panel: { backgroundColor: '#fff', borderColor: '#dce4de', borderWidth: 1, padding: 18 },
  panelTitle: { color: '#17221d', fontSize: 20, fontWeight: '700', marginBottom: 12 },
  row: { borderTopColor: '#dce4de', borderTopWidth: 1, paddingVertical: 12 },
  rowText: { color: '#17221d' },
  status: { color: '#1f6b4d', fontSize: 12, marginTop: 4, textTransform: 'capitalize' },
  muted: { color: '#6d7a72' },
  error: { color: '#963e2a', marginVertical: 12 },
  button: { backgroundColor: '#1f6b4d', marginTop: 18, padding: 14, alignItems: 'center' },
  buttonText: { color: '#fff', fontWeight: '700' },
})
