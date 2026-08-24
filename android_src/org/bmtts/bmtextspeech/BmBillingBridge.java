package org.bmtts.bmtextspeech;

import android.app.Activity;
import android.content.Context;
import android.content.SharedPreferences;
import android.util.Log;

import com.android.billingclient.api.AcknowledgePurchaseParams;
import com.android.billingclient.api.BillingClient;
import com.android.billingclient.api.BillingClientStateListener;
import com.android.billingclient.api.BillingFlowParams;
import com.android.billingclient.api.BillingResult;
import com.android.billingclient.api.PendingPurchasesParams;
import com.android.billingclient.api.ProductDetails;
import com.android.billingclient.api.ProductDetailsResponseListener;
import com.android.billingclient.api.Purchase;
import com.android.billingclient.api.PurchasesResponseListener;
import com.android.billingclient.api.PurchasesUpdatedListener;
import com.android.billingclient.api.QueryProductDetailsParams;
import com.android.billingclient.api.QueryProductDetailsResult;
import com.android.billingclient.api.QueryPurchasesParams;

import org.json.JSONException;
import org.json.JSONObject;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Locale;

/**
 * Google Play Billing bridge for the non-consumable voice-clone entitlement.
 *
 * <p>The displayed price always comes from ProductDetails. Kazakhstan's
 * console price is guarded at exactly 500 KZT; prices for every other country
 * remain the localized values configured by Google Play. Pending purchases do
 * not unlock the feature. The free-use counter is incremented only by the
 * explicit recordCompletedGeneration call made after final audio validation.</p>
 *
 * <p>This is a client-only entitlement implementation. A future backend can
 * replace the ownership decision with Purchases.products verification without
 * changing the Python/UI contract exposed by getStateJson.</p>
 */
public final class BmBillingBridge {
    private static final String TAG = "BmBillingBridge";
    private static final String PREFS = "bm_voice_clone_billing";
    private static final String KEY_COMPLETED = "completed_clone_generations";
    private static final String KEY_LIFETIME = "voice_clone_lifetime_owned";
    private static final String KEY_LAST_VERIFIED = "last_play_verified_at_ms";
    private static final String KEY_TOKEN_HASH = "last_purchase_token_sha256";
    private static final String DEFAULT_PRODUCT_ID = "voice_clone_lifetime";
    private static final int DEFAULT_FREE_LIMIT = 10;
    private static final long EXPECTED_KZT_PRICE_MICROS = 500_000_000L;

    private static final Object LOCK = new Object();
    private static BillingClient billingClient;
    private static Context appContext;
    private static String productId = DEFAULT_PRODUCT_ID;
    private static int freeLimit = DEFAULT_FREE_LIMIT;
    private static boolean connecting = false;
    private static boolean connected = false;
    private static boolean productAvailable = false;
    private static boolean purchasePending = false;
    private static boolean purchaseLaunchRequested = false;
    private static boolean priceConfigurationOk = true;
    private static ProductDetails currentProduct;
    private static ProductDetails.OneTimePurchaseOfferDetails currentOffer;
    private static String localizedPrice = "";
    private static String currencyCode = "";
    private static long priceMicros = 0L;
    private static String status = "idle";
    private static int responseCode = BillingClient.BillingResponseCode.OK;
    private static long eventVersion = 0L;

    private BmBillingBridge() {}

    private static final PurchasesUpdatedListener PURCHASES_UPDATED_LISTENER =
            new PurchasesUpdatedListener() {
                @Override
                public void onPurchasesUpdated(
                        BillingResult result,
                        List<Purchase> purchases) {
                    int code = result.getResponseCode();
                    synchronized (LOCK) {
                        responseCode = code;
                        eventVersion++;
                    }
                    if (code == BillingClient.BillingResponseCode.OK) {
                        processPurchases(purchases, false);
                    } else if (code == BillingClient.BillingResponseCode.USER_CANCELED) {
                        setStatus("purchase_cancelled", code);
                    } else if (code == BillingClient.BillingResponseCode.ITEM_ALREADY_OWNED) {
                        refreshOwnedPurchases();
                    } else {
                        Log.w(TAG, "Purchase update failed: " + code + " " + safeMessage(result));
                        setStatus("purchase_error", code);
                    }
                }
            };

    public static void initialize(
            final Activity activity,
            final String requestedProductId,
            final int requestedFreeLimit) {
        if (activity == null) {
            setStatus("billing_unavailable", BillingClient.BillingResponseCode.ERROR);
            return;
        }
        synchronized (LOCK) {
            appContext = activity.getApplicationContext();
            String cleanId = requestedProductId == null ? "" : requestedProductId.trim();
            if (!cleanId.isEmpty()) {
                productId = cleanId;
            }
            freeLimit = Math.max(0, requestedFreeLimit);
        }
        activity.runOnUiThread(new Runnable() {
            @Override
            public void run() {
                connect(activity);
            }
        });
    }

    private static void connect(final Activity activity) {
        synchronized (LOCK) {
            if (billingClient != null && billingClient.isReady()) {
                connected = true;
                connecting = false;
                setStatusLocked("ready", BillingClient.BillingResponseCode.OK);
                refreshOwnedPurchases();
                queryProductDetails(activity, false);
                return;
            }
            if (connecting) {
                return;
            }
            if (billingClient == null) {
                PendingPurchasesParams pending = PendingPurchasesParams.newBuilder()
                        .enableOneTimeProducts()
                        .build();
                billingClient = BillingClient.newBuilder(activity.getApplicationContext())
                        .setListener(PURCHASES_UPDATED_LISTENER)
                        .enablePendingPurchases(pending)
                        .enableAutoServiceReconnection()
                        .build();
            }
            connecting = true;
            connected = false;
            setStatusLocked("connecting", BillingClient.BillingResponseCode.OK);
        }
        billingClient.startConnection(new BillingClientStateListener() {
            @Override
            public void onBillingSetupFinished(BillingResult result) {
                int code = result.getResponseCode();
                synchronized (LOCK) {
                    connecting = false;
                    connected = code == BillingClient.BillingResponseCode.OK;
                }
                if (code == BillingClient.BillingResponseCode.OK) {
                    setStatus("ready", code);
                    refreshOwnedPurchases();
                    boolean launch;
                    synchronized (LOCK) {
                        launch = purchaseLaunchRe²È="24€€€€€€€€€€€ô(€€€€€€€€€€€€€€€€€€€½¹¹•Ğ¡…Ñ¥Ù¥Ñä¤ì(€€€€€€€€€€€€€€€€€€€Í•ÑMÑ…ÑÕÌ ‰½¹¹•Ñ¥¹œˆ°	¥±±¥¹±¥•¹Ğ¹	¥±±¥¹I•ÍÁ½¹Í•½‘”¹=,¤ì(€€€€€€€€€€€€€€€€€€€É•ÑÕÉ¸ì(€€€€€€€€€€€€€€€ô(€€€€€€€€€€€€€€€€¼¼AÉ½‘ÕÑ•Ñ…¥±Ì…¹½™™•ÈÑ½­•¹Ì…¸‰•½µ”ÍÑ…±”¸±İ…åÌ(€€€€€€€€€€€€€€€€¼¼É•™É•Í ¥µµ•‘¥…Ñ•±ä‰•™½É”½Á•¹¥¹œÑ¡”½½±”A±…äÍ¡••Ğ¸(€€€€€€€€€€€€€€€ÅÕ•ÉåAÉ½‘ÕÑ•Ñ…¥±Ì¡…Ñ¥Ù¥Ñä°ÑÉÕ”¤ì(€€€€€€€€€€€ô(€€€€€€€ô¤ì(€€€€€€€É•ÑÕÉ¸ÑÉÕ”ì(€€€ô((€€€ÁÉ¥Ù…Ñ”ÍÑ…Ñ¥ŒÙ½¥±…Õ¹¡	¥±±¥¹±½Ü (€€€€€€€€€€€Ñ¥Ù¥Ñä…Ñ¥Ù¥Ñä°(€€€€€€€€€€€AÉ½‘ÕÑ•Ñ…¥±Ì‘•Ñ…¥±Ì°(€€€€€€€€€€€AÉ½‘ÕÑ•Ñ…¥±Ì¹=¹•Q¥µ•AÕÉ¡…Í•=™™•É•Ñ…¥±Ì½™™•È¤ì(€€€€€€€¥˜€¡…Ñ¥Ù¥Ñä€ôô¹Õ±°ñğ‘•Ñ…¥±Ì€ôô¹Õ±°ñğ½™™•È€ôô¹Õ±°¤ì(€€€€€€€€€€€Í•ÑMÑ…ÑÕÌ ‰ÁÉ½‘ÕÑ}Õ¹…Ù…¥±…‰±”ˆ°	¥±±¥¹±¥•¹Ğ¹	¥±±¥¹I•ÍÁ½¹Í•½‘”¹%Q5}U9Y%1	1¤ì(€€€€€€€€€€€É•ÑÕÉ¸ì(€€€€€€€ô(€€€€€€€	¥±±¥¹±½İA…É…µÌ¹AÉ½‘ÕÑ•Ñ…¥±ÍA…É…µÌ¹	Õ¥±‘•È¥Ñ•´€ô(€€€€€€€€€€€€€€€	¥±±¥¹±½İA…É…µÌ¹AÉ½‘ÕÑ•Ñ…¥±ÍA…É…µÌ¹¹•İ	Õ¥±‘•È ¤(€€€€€€€€€€€€€€€€€€€€€€€€¹Í•ÑAÉ½‘ÕÑ•Ñ…¥±Ì¡‘•Ñ…¥±Ì¤ì(€€€€€€€MÑÉ¥¹œ½™™•ÉQ½­•¸€ô½™™•È¹•Ñ=™™•ÉQ½­•¸ ¤ì(€€€€€€€¥˜€¡½™™•ÉQ½­•¸€„ô¹Õ±°€˜˜€…½™™•ÉQ½­•¸¹¥ÍµÁÑä ¤¤ì(€€€€€€€€€€€¥Ñ•´¹Í•Ñ=™™•ÉQ½­•¸¡½™™•ÉQ½­•¸¤ì(€€€€€€€ô(€€€€€€€	¥±±¥¹±½İA…É…µÌÁ…É…µÌ€ô	¥±±¥¹±½İA…É…µÌ¹¹•İ	Õ¥±‘•È ¤(€€€€€€€€€€€€€€€€¹Í•ÑAÉ½‘ÕÑ•Ñ…¥±ÍA…É…µÍ1¥ÍĞ¡½±±•Ñ¥½¹Ì¹Í¥¹±•Ñ½¹1¥ÍĞ¡¥Ñ•´¹‰Õ¥± ¤¤¤(€€€€€€€€€€€€€€€€¹‰Õ¥± ¤ì(€€€€€€€	¥±±¥¹I•ÍÕ±ĞÉ•ÍÕ±Ğ€ô‰¥±±¥¹±¥•¹Ğ¹±…Õ¹¡	¥±±¥¹±½Ü¡…Ñ¥Ù¥Ñä°Á…É…µÌ¤ì(€€€€€€€¥¹Ğ½‘”€ôÉ•ÍÕ±Ğ¹•ÑI•ÍÁ½¹Í•½‘” ¤ì(€€€€€€€¥˜€¡½‘”€ôô	¥±±¥¹±¥•¹Ğ¹	¥±±¥¹I•ÍÁ½¹Í•½‘”¹=,¤ì(€€€€€€€€€€€Í•ÑMÑ…ÑÕÌ ‰ÁÕÉ¡…Í•}ÍÑ…ÉÑ•ˆ°½‘”¤ì(€€€€€€€ô•±Í”¥˜€¡½‘”€ôô	¥±±¥¹±¥•¹Ğ¹	¥±±¥¹I•ÍÁ½¹Í•½‘”¹%Q5}1Ie}=]9¤ì(€€€€€€€€€€€É•™É•Í¡=İ¹•‘AÕÉ¡…Í•Ì ¤ì(€€€€€€€ô•±Í”ì(€€€€€€€€€€€1½œ¹Ü¡Q°€‰½Õ±¹½Ğ±…Õ¹ ÁÕÉ¡…Í”è€ˆ€¬½‘”€¬€ˆ€ˆ€¬Í…™•5•ÍÍ…”¡É•ÍÕ±Ğ¤¤ì(€€€€€€€€€€€Í•ÑMÑ…ÑÕÌ ‰ÁÕÉ¡…Í•}•ÉÉ½Èˆ°½‘”¤ì(€€€€€€€ô(€€€ô((€€€ÁÕ‰±¥ŒÍÑ…Ñ¥Œ‰½½±•…¸…¹•¹•É…Ñ”¡Ñ¥Ù¥Ñä…Ñ¥Ù¥Ñä¤ì(€€€€€€€M¡…É•‘AÉ•™•É•¹•ÌÁÉ•™Ì€ôÁÉ•™•É•¹•Ì¡…Ñ¥Ù¥Ñä¤ì(€€€€€€€¥˜€¡ÁÉ•™Ì€ôô¹Õ±°¤ì(€€€€€€€€€€€É•ÑÕÉ¸™…±Í”ì(€€€€€€€ô(€€€€€€€É•ÑÕÉ¸ÁÉ•™Ì¹•Ñ	½½±•…¸¡-e}1%Q%5°™…±Í”¤(€€€€€€€€€€€€€€€ñğÁÉ•™Ì¹•Ñ%¹Ğ¡-e}=5A1Q°€À¤€ğ™É••1¥µ¥Ğì(€€€ô((€€€ÁÕ‰±¥ŒÍÑ…Ñ¥Œ¥¹ĞÉ•½É‘½µÁ±•Ñ•‘•¹•É…Ñ¥½¸¡Ñ¥Ù¥Ñä…Ñ¥Ù¥Ñä¤ì(€€€€€€€M¡…É•‘AÉ•™•É•¹•ÌÁÉ•™Ì€ôÁÉ•™•É•¹•Ì¡…Ñ¥Ù¥Ñä¤ì(€€€€€€€¥˜€¡ÁÉ•™Ì€ôô¹Õ±°¤ì(€€€€€€€€€€€É•ÑÕÉ¸™É••1¥µ¥Ğì(€€€€€€€ô(€€€€€€€Íå¹¡É½¹¥é•€¡1=,¤ì(€€€€€€€€€€€¥¹Ğ½µÁ±•Ñ•€ô5…Ñ ¹µ…à À°ÁÉ•™Ì¹•Ñ%¹Ğ¡-e}=5A1Q°€À¤¤ì(€€€€€€€€€€€¥˜€ …ÁÉ•™Ì¹•Ñ	½½±•…¸¡-e}1%Q%5°™…±Í”¤€˜˜½µÁ±•Ñ•€ğ™É••1¥µ¥Ğ¤ì(€€€€€€€€€€€€€€€½µÁ±•Ñ•¬¬ì(€€€€€€€€€€€€€€€ÁÉ•™Ì¹•‘¥Ğ ¤¹ÁÕÑ%¹Ğ¡-e}=5A1Q°½µÁ±•Ñ•¤¹…ÁÁ±ä ¤ì(€€€€€€€€€€€€€€€•Ù•¹ÑY•ÉÍ¥½¸¬¬ì(€€€€€€€€€€€ô(€€€€€€€€€€€É•ÑÕÉ¸½µÁ±•Ñ•ì(€€€€€€€ô(€€€ô((€€€ÁÕ‰±¥ŒÍÑ…Ñ¥ŒMÑÉ¥¹œ•ÑMÑ…Ñ•)Í½¸¡Ñ¥Ù¥Ñä…Ñ¥Ù¥Ñä¤ì(€€€€€€€M¡…É•‘AÉ•™•É•¹•ÌÁÉ•™Ì€ôÁÉ•™•É•¹•Ì¡…Ñ¥Ù¥Ñä¤ì(€€€€€€€¥¹Ğ½µÁ±•Ñ•€ôÁÉ•™Ì€ôô¹Õ±°€ü™É••1¥µ¥Ğ€è5…Ñ ¹µ…à À°ÁÉ•™Ì¹•Ñ%¹Ğ¡-e}=5A1Q°€À¤¤ì(€€€€€€€‰½½±•…¸½İ¹•€ôÁÉ•™Ì€„ô¹Õ±°€˜˜ÁÉ•™Ì¹•Ñ	½½±•…¸¡-e}1%Q%5°™…±Í”¤ì(€€€€€€€±½¹œÙ•É¥™¥•€ôÁÉ•™Ì€ôô¹Õ±°€ü€Á0€èÁÉ•™Ì¹•Ñ1½¹œ¡-e}1MQ}YI%%°€Á0¤ì(€€€€€€€)M=9=‰©•ĞÉ•ÍÕ±Ğ€ô¹•Ü)M=9=‰©•Ğ ¤ì(€€€€€€€Íå¹¡É½¹¥é•€¡1=,¤ì(€€€€€€€€€€€ÑÉäì(€€€€€€€€€€€€€€€É•ÍÕ±Ğ¹ÁÕĞ ‰ÁÉ½‘ÕÑ%ˆ°ÁÉ½‘ÕÑ%¤ì(€€€€€€€€€€€€€€€É•ÍÕ±Ğ¹ÁÕĞ ‰‰¥±±¥¹Ù…¥±…‰±”ˆ°½¹¹•Ñ•¤ì(€€€€€€€€€€€€€€€É•ÍÕ±Ğ¹ÁÕĞ ‰½¹¹•Ñ•ˆ°½¹¹•Ñ•¤ì(€€€€€€€€€€€€€€€É•ÍÕ±Ğ¹ÁÕĞ ‰ÁÉ½‘ÕÑÙ…¥±…‰±”ˆ°ÁÉ½‘ÕÑÙ…¥±…‰±”¤ì(€€€€€€€€€€€€€€€É•ÍÕ±Ğ¹ÁÕĞ ‰±¥™•Ñ¥µ•=İ¹•ˆ°½İ¹•¤ì(€€€€€€€€€€€€€€€É•ÍÕ±Ğ¹ÁÕĞ ‰ÁÕÉ¡…Í•A•¹‘¥¹œˆ°ÁÕÉ¡…Í•A•¹‘¥¹œ¤ì(€€€€€€€€€€€€€€€É•ÍÕ±Ğ¹ÁÕĞ ‰™É••1¥µ¥Ğˆ°™É••1¥µ¥Ğ¤ì(€€€€€€€€€€€€€€€É•ÍÕ±Ğ¹ÁÕĞ ‰½µÁ±•Ñ•‘•¹•É…Ñ¥½¹Ìˆ°½µÁ±•Ñ•¤ì(€€€€€€€€€€€€€€€É•ÍÕ±Ğ¹ÁÕĞ ‰É•µ…¥¹¥¹É•”ˆ°5…Ñ ¹µ…à À°™É••1¥µ¥Ğ€´½µÁ±•Ñ•¤¤ì(€€€€€€€€€€€€€€€É•ÍÕ±Ğ¹ÁÕĞ ‰…¹•¹•É…Ñ”ˆ°½İ¹•ñğ½µÁ±•Ñ•€ğ™É••1¥µ¥Ğ¤ì(€€€€€€€€€€€€€€€É•ÍÕ±Ğ¹ÁÕĞ ‰±½…±¥é•‘AÉ¥”ˆ°±½…±¥é•‘AÉ¥”¤ì(€€€€€€€€€€€€€€€É•ÍÕ±Ğ¹ÁÕĞ ‰ÕÉÉ•¹å½‘”ˆ°ÕÉÉ•¹å½‘”¤ì(€€€€€€€€€€€€€€€É•ÍÕ±Ğ¹ÁÕĞ ‰ÁÉ¥•5¥É½Ìˆ°ÁÉ¥•5¥É½Ì¤ì(€€€€€€€€€€€€€€€É•ÍÕ±Ğ¹ÁÕĞ ‰ÁÉ¥•½¹™¥ÕÉ…Ñ¥½¹=¬ˆ°ÁÉ¥•½¹™¥ÕÉ…Ñ¥½¹=¬¤ì(€€€€€€€€€€€€€€€É•ÍÕ±Ğ¹ÁÕĞ ‰ÍÑ…ÑÕÌˆ°ÍÑ…ÑÕÌ¤ì(€€€€€€€€€€€€€€€É•ÍÕ±Ğ¹ÁÕĞ ‰É•ÍÁ½¹Í•½‘”ˆ°É•ÍÁ½¹Í•½‘”¤ì(€€€€€€€€€€€€€€€É•ÍÕ±Ğ¹ÁÕĞ ‰•Ù•¹ÑY•ÉÍ¥½¸ˆ°•Ù•¹ÑY•ÉÍ¥½¸¤ì(€€€€€€€€€€€€€€€É•ÍÕ±Ğ¹ÁÕĞ ‰±…ÍÑY•É¥™¥•‘Ñ5Ìˆ°Ù•É¥™¥•¤ì(€€€€€€€€€€€€€€€É•ÍÕ±Ğ¹ÁÕĞ ‰Ù•É¥™¥…Ñ¥½¹5½‘”ˆ°€‰Á±…å}±¥•¹Ñ}½¹±äˆ¤ì(€€€€€€€€€€€€€€€É•ÍÕ±Ğ¹ÁÕĞ ‰‰¥±±¥¹1¥‰É…Éäˆ°€ˆä¸Ä¸Àˆ¤ì(€€€€€€€€€€€ô…Ñ €¡)M=9á•ÁÑ¥½¸¥¹½É•¤ì(€€€€€€€€€€€€€€€É•ÑÕÉ¸€‰íp‰ÍÑ…ÑÕÍpˆép‰‰¥±±¥¹}Õ¹…Ù…¥±…‰±•p‰ôˆì(€€€€€€€€€€€ô(€€€€€€€ô(€€€€€€€É•ÑÕÉ¸É•ÍÕ±Ğ¹Ñ½MÑÉ¥¹œ ¤ì(€€€ô((€€€ÁÕ‰±¥ŒÍÑ…Ñ¥ŒÙ½¥•¹‘½¹¹•Ñ¥½¸ ¤ì(€€€€€€€Íå¹¡É½¹¥é•€¡1=,¤ì(€€€€€€€€€€€¥˜€¡‰¥±±¥¹±¥•¹Ğ€„ô¹Õ±°¤ì(€€€€€€€€€€€€€€€ÑÉäì(€€€€€€€€€€€€€€€€€€€‰¥±±¥¹±¥•¹Ğ¹•¹‘½¹¹•Ñ¥½¸ ¤ì(€€€€€€€€€€€€€€€ô…Ñ €¡á•ÁÑ¥½¸¥¹½É•¤ì(€€€€€€€€€€€€€€€€€€€€¼¼ÁÀÍ¡ÕÑ‘½İ¸µÕÍĞÉ•µ…¥¸Í…™”½¸=4A±…äMÑ½É”‰Õ¥±‘Ì¸(€€€€€€€€€€€€€€€ô(€€€€€€€€€€€ô(€€€€€€€€€€€‰¥±±¥¹±¥•¹Ğ€ô¹Õ±°ì(€€€€€€€€€€€½¹¹•Ñ¥¹œ€ô™…±Í”ì(€€€€€€€€€€€½¹¹•Ñ•€ô™…±Í”ì(€€€€€€€€€€€ÕÉÉ•¹ÑAÉ½‘ÕĞ€ô¹Õ±°ì(€€€€€€€€€€€ÕÉÉ•¹Ñ=™™•È€ô¹Õ±°ì(€€€€€€€€€€€ÁÉ½‘ÕÑÙ…¥±…‰±”€ô™…±Í”ì(€€€€€€€€€€€ÁÕÉ¡…Í•1…Õ¹¡I•ÅÕ•ÍÑ•€ô™…±Í”ì(€€€€€€€€€€€ÍÑ…ÑÕÌ€ô€‰¥‘±”ˆì(€€€€€€€€€€€•Ù•¹ÑY•ÉÍ¥½¸¬¬ì(€€€€€€€ô(€€€ô((€€€ÁÉ¥Ù…Ñ”ÍÑ…Ñ¥Œ‰½½±•…¸¥Í±¥•¹ÑI•…‘ä ¤ì(€€€€€€€Íå¹¡É½¹¥é•€¡1=,¤ì(€€€€€€€€€€€É•ÑÕÉ¸‰¥±±¥¹±¥•¹Ğ€„ô¹Õ±°€˜˜‰¥±±¥¹±¥•¹Ğ¹¥ÍI•…‘ä ¤ì(€€€€€€€ô(€€€ô((€€€ÁÉ¥Ù…Ñ”ÍÑ…Ñ¥Œ‰½½±•…¸¥Í1¥™•Ñ¥µ•=İ¹• ¤ì(€€€€€€€M¡…É•‘AÉ•™•É•¹•ÌÁÉ•™Ì€ôÁÉ•™•É•¹•Ì ¤ì(€€€€€€€É•ÑÕÉ¸ÁÉ•™Ì€„ô¹Õ±°€˜˜ÁÉ•™Ì¹•Ñ	½½±•…¸¡-e}1%Q%5°™…±Í”¤ì(€€€ô((€€€ÁÉ¥Ù…Ñ”ÍÑ…Ñ¥ŒM¡…É•‘AÉ•™•É•¹•ÌÁÉ•™•É•¹•Ì¡Ñ¥Ù¥Ñä…Ñ¥Ù¥Ñä¤ì(€€€€€€€¥˜€¡…Ñ¥Ù¥Ñä€„ô¹Õ±°¤ì(€€€€€€€€€€€Íå¹¡É½¹¥é•€¡1=,¤ì(€€€€€€€€€€€€€€€…ÁÁ½¹Ñ•áĞ€ô…Ñ¥Ù¥Ñä¹•ÑÁÁ±¥…Ñ¥½¹½¹Ñ•áĞ ¤ì(€€€€€€€€€€€ô(€€€€€€€ô(€€€€€€€É•ÑÕÉ¸ÁÉ•™•É•¹•Ì ¤ì(€€€ô((€€€ÁÉ¥Ù…Ñ”ÍÑ…Ñ¥ŒM¡…É•‘AÉ•™•É•¹•ÌÁÉ•™•É•¹•Ì ¤ì(€€€€€€€½¹Ñ•áĞ½¹Ñ•áĞì(€€€€€€€Íå¹¡É½¹¥é•€¡1=,¤ì(€€€€€€€€€€€½¹Ñ•áĞ€ô…ÁÁ½¹Ñ•áĞì(€€€€€€€ô(€€€€€€€É•ÑÕÉ¸½¹Ñ•áĞ€ôô¹Õ±°€ü¹Õ±°€è½¹Ñ•áĞ¹•ÑM¡…É•‘AÉ•™•É•¹•Ì¡AIL°½¹Ñ•áĞ¹5=}AI%YQ¤ì(€€€ô((€€€ÁÉ¥Ù…Ñ”ÍÑ…Ñ¥ŒÙ½¥Í•ÑMÑ…ÑÕÌ¡MÑÉ¥¹œÙ…±Õ”°¥¹Ğ½‘”¤ì(€€€€€€€Íå¹¡É½¹¥é•€¡1=,¤ì(€€€€€€€€€€€Í•ÑMÑ…ÑÕÍ1½­•¡Ù…±Õ”°½‘”¤ì(€€€€€€€ô(€€€ô((€€€ÁÉ¥Ù…Ñ”ÍÑ…Ñ¥ŒÙ½¥Í•ÑMÑ…ÑÕÍ1½­•¡MÑÉ¥¹œÙ…±Õ”°¥¹Ğ½‘”¤ì(€€€€€€€ÍÑ…ÑÕÌ€ôÙ…±Õ”€ôô¹Õ±°€ü€‰‰¥±±¥¹}Õ¹…Ù…¥±…‰±”ˆ€èÙ…±Õ”ì(€€€€€€€É•ÍÁ½¹Í•½‘”€ô½‘”ì(€€€€€€€•Ù•¹ÑY•ÉÍ¥½¸¬¬ì(€€€ô((€€€ÁÉ¥Ù…Ñ”ÍÑ…Ñ¥ŒMÑÉ¥¹œÍ…™•5•ÍÍ…”¡	¥±±¥¹I•ÍÕ±ĞÉ•ÍÕ±Ğ¤ì(€€€€€€€¥˜€¡É•ÍÕ±Ğ€ôô¹Õ±°ñğÉ•ÍÕ±Ğ¹•Ñ•‰Õ5•ÍÍ…” ¤€ôô¹Õ±°¤ì(€€€€€€€€€€€É•ÑÕÉ¸€ˆˆì(€€€€€€€ô(€€€€€€€MÑÉ¥¹œµ•ÍÍ…”€ôÉ•ÍÕ±Ğ¹•Ñ•‰Õ5•ÍÍ…” ¤¹É•Á±…” q¸œ°€œ€œ¤¹É•Á±…” qÈœ°€œ€œ¤¹ÑÉ¥´ ¤ì(€€€€€€€É•ÑÕÉ¸µ•ÍÍ…”¹±•¹Ñ  ¤€ø€ÈĞÀ€üµ•ÍÍ…”¹ÍÕ‰ÍÑÉ¥¹œ À°€ÈĞÀ¤€èµ•ÍÍ…”ì(€€€ô((€€€ÁÉ¥Ù…Ñ”ÍÑ…Ñ¥ŒMÑÉ¥¹œ¹½¹9Õ±°¡MÑÉ¥¹œÙ…±Õ”¤ì(€€€€€€€É•ÑÕÉ¸Ù…±Õ”€ôô¹Õ±°€ü€ˆˆ€èÙ…±Õ”ì(€€€ô((€€€ÁÉ¥Ù…Ñ”ÍÑ…Ñ¥ŒMÑÉ¥¹œÍ¡„ÈÔØ¡MÑÉ¥¹œÙ…±Õ”¤ì(€€€€€€€¥˜€¡Ù…±Õ”€ôô¹Õ±°ñğÙ…±Õ”¹¥ÍµÁÑä ¤¤ì(€€€€€€€€€€€É•ÑÕÉ¸€ˆˆì(€€€€€€€ô(€€€€€€€ÑÉäì(€€€€€€€€€€€5•ÍÍ…•¥•ÍĞ‘¥•ÍĞ€ô5•ÍÍ…•¥•ÍĞ¹•Ñ%¹ÍÑ…¹” ‰M!´ÈÔØˆ¤ì(€€€€€€€€€€€‰åÑ•mt‘…Ñ„€ô‘¥•ÍĞ¹‘¥•ÍĞ¡Ù…±Õ”¹•Ñ	åÑ•Ì¡MÑ…¹‘…É‘¡…ÉÍ•ÑÌ¹UQ|à¤¤ì(€€€€€€€€€€€MÑÉ¥¹	Õ¥±‘•È½ÕĞ€ô¹•ÜMÑÉ¥¹	Õ¥±‘•È¡‘…Ñ„¹±•¹Ñ €¨€È¤ì(€€€€€€€€€€€™½È€¡‰åÑ”¥Ñ•´€è‘…Ñ„¤ì(€€€€€€€€€€€€€€€½ÕĞ¹…ÁÁ•¹¡MÑÉ¥¹œ¹™½Éµ…Ğ¡1½…±”¹I==P°€ˆ”ÀÉàˆ°¥Ñ•´€˜€Áá™˜¤¤ì(€€€€€€€€€€€ô(€€€€€€€€€€€É•ÑÕÉ¸½ÕĞ¹Ñ½MÑÉ¥¹œ ¤ì(€€€€€€€ô…Ñ €¡á•ÁÑ¥½¸•ÉÉ½È¤ì(€€€€€€€€€€€É•ÑÕÉ¸€ˆˆì(€€€€€€€ô(€€€ô)ô(