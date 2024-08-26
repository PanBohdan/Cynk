// Import the SDK
import { DiscordSDK } from "@discord/embedded-app-sdk";

import "../../frontend/getting-started-activity/client/style.css";
import rocketLogo from '/frontend/getting-started-activity/client/rocket.png';

// Instantiate the SDK
const discordSdk = new DiscordSDK(import.meta.env.VITE_DISCORD_CLIENT_ID);

setupDiscordSdk().then(() => {
  console.log("Discord SDK is ready");
});

async function setupDiscordSdk() {
  await discordSdk.ready();
}

document.querySelector('#app').innerHTML = `
  <div>
    <iframe >
  </div>
`;
