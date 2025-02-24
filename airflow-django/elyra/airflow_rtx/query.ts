import { useQuery } from '@tanstack/react-query';
import axios from 'axios';

// Define the response type based on your structure.
export interface AllDagLogsResponse {
  all_logs: Record<
    string, // DAG ID
    Record<
      string, // DAG run ID; may be empty if no logs exist
      Record<
        string, // Task ID
        string  // Log string
      >
    >
  >;
}

const fetchAllDagLogs = async (): Promise<AllDagLogsResponse> => {
  const response = await axios.get<AllDagLogsResponse>('/airflow/get-all-dag-logs/');
  return response.data;
};

export const useAllDagLogs = () => {
  return useQuery<AllDagLogsResponse, Error>(['allDagLogs'], fetchAllDagLogs);
};
