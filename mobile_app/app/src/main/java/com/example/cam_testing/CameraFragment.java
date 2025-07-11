package com.example.cam_testing;

import android.os.Bundle;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;

import androidx.fragment.app.Fragment;
import androidx.fragment.app.FragmentTransaction;

import java.util.HashMap;
import java.util.Map;

public class CameraFragment extends Fragment {

    private final Map<String, String> cameraUrls = new HashMap<String, String>() {{
        put("camera1", "http://192.168.0.179:5002/video_feed");
        put("camera2", "http://192.168.251.216:5005/video_feed");
        put("camera3", "http://192.168.251.223:5004/video_feed");
        put("camera4", "http://192.168.0.141:5004/video_feed");
        put("camera5", "http://192.168.0.179:5002/video_feed");
    }};

    @Override
    public View onCreateView(LayoutInflater inflater, ViewGroup container, Bundle savedInstanceState) {
        View view = inflater.inflate(R.layout.fragment_camera, container, false);

        // Setup WebViews for Live Feed
        setupCameraWebView(view, R.id.camera1WebView, "camera1");
        setupCameraWebView(view, R.id.camera2WebView, "camera2");
        setupCameraWebView(view, R.id.camera3WebView, "camera3");
        setupCameraWebView(view, R.id.camera4WebView, "camera4");
        setupCameraWebView(view, R.id.camera5WebView, "camera5");

        // Setup Fullscreen Buttons
        setupCameraButton(view, R.id.camera1Button, "camera1");
        setupCameraButton(view, R.id.camera2Button, "camera2");
        setupCameraButton(view, R.id.camera3Button, "camera3");
        setupCameraButton(view, R.id.camera4Button, "camera4");
        setupCameraButton(view, R.id.camera5Button, "camera5");

        return view;
    }

    private void setupCameraWebView(View view, int webViewId, String cameraKey) {
        WebView webView = view.findViewById(webViewId);
        String cameraUrl = cameraUrls.get(cameraKey);

        if (cameraUrl != null) {
            WebSettings webSettings = webView.getSettings();
            webSettings.setJavaScriptEnabled(true); // Enable JavaScript for smooth streaming
            webSettings.setLoadWithOverviewMode(true);
            webSettings.setUseWideViewPort(true);

            webView.setWebViewClient(new WebViewClient());
            webView.loadUrl(cameraUrl);
        }
    }

    private void setupCameraButton(View view, int buttonId, final String cameraKey) {
        Button button = view.findViewById(buttonId);
        button.setOnClickListener(new View.OnClickListener() {
            @Override
            public void onClick(View v) {
                String cameraUrl = cameraUrls.get(cameraKey);
                if (cameraUrl != null) {
                    openFullScreenCamera(cameraUrl);
                }
            }
        });
    }

    private void openFullScreenCamera(String cameraUrl) {
        FullScreenCameraFragment fullScreenFragment = FullScreenCameraFragment.newInstance(cameraUrl);
        FragmentTransaction transaction = requireActivity().getSupportFragmentManager().beginTransaction();
        transaction.replace(R.id.fragment_container, fullScreenFragment);
        transaction.addToBackStack(null);
        transaction.commit();
    }
}
