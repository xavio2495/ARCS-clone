package com.example.cam_testing;

import android.os.Bundle;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.TextView;
import android.widget.ImageView;
import androidx.fragment.app.Fragment;
import com.squareup.picasso.Picasso;
import org.json.JSONException;
import org.json.JSONObject;
import io.socket.client.IO;
import io.socket.client.Socket;
import io.socket.emitter.Emitter;
import java.net.URISyntaxException;

public class AlertFragment extends Fragment {

    private Socket socket;
    private TextView alertTextView;
    private ImageView alertImageView;

    @Override
    public View onCreateView(LayoutInflater inflater, ViewGroup container, Bundle savedInstanceState) {
        View view = inflater.inflate(R.layout.activity_alert_fragment, container, false);
        alertTextView = view.findViewById(R.id.alertText);
        alertImageView = view.findViewById(R.id.alertImage);

        try {
            IO.Options options = IO.Options.builder()
                    .setTransports(new String[]{"websocket"}) // Use WebSocket only
                    .setReconnection(true) // Auto-reconnect enabled
                    .setReconnectionAttempts(5) // Retry up to 5 times
                    .setReconnectionDelay(2000) // Wait 2 seconds before retrying
                    .build();

            socket = IO.socket("http://192.168.0.229:5000", options);
            socket.connect();

            // Log connection events
            socket.on(Socket.EVENT_CONNECT, args -> getActivity().runOnUiThread(() ->
                    System.out.println("✅ Connected to WebSocket!")
            ));
            socket.on(Socket.EVENT_DISCONNECT, args -> getActivity().runOnUiThread(() ->
                    System.out.println("⚠️ Disconnected from WebSocket!")
            ));

            socket.on("new_alert", onNewAlert);
        } catch (URISyntaxException e) {
            e.printStackTrace();
        }

        return view;
    }

    private final Emitter.Listener onNewAlert = new Emitter.Listener() {
        @Override
        public void call(final Object... args) {
            if (getActivity() == null) return;

            getActivity().runOnUiThread(new Runnable() {
                @Override
                public void run() {
                    JSONObject data = (JSONObject) args[0];
                    try {
                        String cctvId = data.getString("cctv_id");
                        String address = data.getString("address");
                        String imageUrl = data.getString("url");

                        alertTextView.setText("Alert from CCTV: " + cctvId + "\nLocation: " + address);
                        Picasso.get().load(imageUrl).into(alertImageView);
                    } catch (JSONException e) {
                        e.printStackTrace();
                    }
                }
            });
        }
    };

    @Override
    public void onDestroy() {
        super.onDestroy();
        if (socket != null) {
            socket.disconnect();
            socket.off("new_alert", onNewAlert);
        }
    }
}
