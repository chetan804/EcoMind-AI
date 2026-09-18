declare module '@react-native-async-storage/async-storage' {
  const AsyncStorage: {
    getItem(key: string): Promise<string | null>
    setItem(key: string, value: string): Promise<void>
    removeItem(key: string): Promise<void>
    clear(): Promise<void>
    multiGet(keys: string[]): Promise<Array<[string, string | null]>>
    multiSet(keyValuePairs: Array<[string, string]>): Promise<void>
  }

  export default AsyncStorage
}
