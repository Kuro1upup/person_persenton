'use client'
import { useCallback } from "react";
import { useTranslation } from "react-i18next";
import { useDispatch } from "react-redux";
import { toast } from "sonner";
import { setPresentationData } from "@/store/slices/presentationGeneration";
import { DashboardApi } from '../../services/api/dashboard';
import {  clearHistory } from "@/store/slices/undoRedoSlice";
import { store } from "@/store/store";


export const usePresentationData = (
  presentationId: string,
  setLoading: (loading: boolean) => void,
  setError: (error: boolean) => void
) => {
  const { t } = useTranslation("presentation");
  const dispatch = useDispatch();

  const fetchUserSlides = useCallback(async () => {
    try {
      const data = await DashboardApi.getPresentation(presentationId);
      if (data) {
        // 获取当前 Redux 状态，保留 webSearchResources 和其他动态数据
        const currentState = store.getState().presentationGeneration.presentationData;

        const mergedData = {
          ...data,
          // 保留当前状态中的动态数据
          webSearchResources: currentState?.webSearchResources ?? data.webSearchResources,
          reference_markers: currentState?.reference_markers ?? data.reference_markers,
        };

        console.log("usePresentationData - current state webSearchResources:", currentState?.webSearchResources);
        console.log("usePresentationData - API data webSearchResources:", data.webSearchResources);
        console.log("usePresentationData - merged webSearchResources:", mergedData.webSearchResources);
        console.log("usePresentationData - current state reference_markers:", currentState?.reference_markers);
        console.log("usePresentationData - API data reference_markers:", data.reference_markers);
        console.log("usePresentationData - merged reference_markers:", mergedData.reference_markers);

        dispatch(setPresentationData(mergedData));
        dispatch(clearHistory());
        setLoading(false);
      }
    } catch (error) {
      setError(true);
      toast.error(t('failed_to_load_presentation'));
      console.error("Error fetching user slides:", error);
      setLoading(false);
    }
  }, [presentationId, dispatch, setLoading, setError, t]);

  return {
    fetchUserSlides,
  };
};
