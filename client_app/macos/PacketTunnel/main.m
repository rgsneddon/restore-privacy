#import <Foundation/Foundation.h>
#import <NetworkExtension/NetworkExtension.h>

// TN3134 Network system extension entry. NSExtensionMain is the app-extension
// runtime and SIGTRAPs (_xpc_copy_xpcservice_dictionary) when this bundle is
// launched as a .systemextension. Do not add an Info.plist XPCService key —
// sysextd then returns "extension category returned error" and refuses to
// replace the staged extension.
int main(int argc, char * argv[]) {
  (void)argc;
  (void)argv;
  @autoreleasepool {
    [NEProvider startSystemExtensionMode];
  }
  dispatch_main();
  return 0;
}
