package com.example.cam_testing;

import android.os.Bundle;
import androidx.fragment.app.Fragment;  // Make sure this is imported
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;

public class AnalyticsFragment extends Fragment {  // Extend from androidx.fragment.app.Fragment

    public AnalyticsFragment() {
        // Required empty public constructor
    }

    @Override
    public View onCreateView(LayoutInflater inflater, ViewGroup container, Bundle savedInstanceState) {
        return inflater.inflate(R.layout.fragment_analytics, container, false);
    }
}
