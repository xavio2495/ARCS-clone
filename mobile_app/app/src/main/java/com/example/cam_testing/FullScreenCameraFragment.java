package com.example.cam_testing;

import android.os.Bundle;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import androidx.annotation.NonNull;
import androidx.annotation.Nullable;
import androidx.fragment.app.Fragment;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;

public class FullScreenCameraFragment extends Fragment {
    private static final String ARG_CAMERA_URL = "camera_url";
    private String cameraUrl;

    public static FullScreenCameraFragment newInstance(String cameraUrl) {
        FullScreenCameraFragment fragment = new FullScreenCameraFragment();
        Bundle args = new Bundle();
        args.putString(ARG_CAMERA_URL, cameraUrl);
        fragment.setArguments(args);
        return fragment;
    }

    @Override
    public void onCreate(@Nullable Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        if (getArguments() != null) {
            cameraUrl = getArguments().getString(ARG_CAMERA_URL);
        }
    }

    @Override
    public View onCreateView(@NonNull LayoutInflater inflater, ViewGroup container, Bundle savedInstanceState) {
        View view = inflater.inflate(R.layout.fragment_full_screen_camera, container, false);
        WebView webView = view.findViewById(R.id.fullScreenWebView);

        if (cameraUrl != null) {
            WebSettings webSettings = webView.getSettings();
            webSettings.setJavaScriptEnabled(true);
            webSettings.setLoadWithOverviewMode(true);
            webSettings.setUseWideViewPort(true);

            webView.setWebViewClient(new WebViewClient());
            webView.loadUrl(cameraUrl);
        }

        return view;
    }
}
