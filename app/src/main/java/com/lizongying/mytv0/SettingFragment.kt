package com.lizongying.mytv0

import MainViewModel
import MainViewModel.Companion.CACHE_FILE_NAME
import android.Manifest
import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.drawable.ColorDrawable
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.util.Log
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import androidx.appcompat.app.AlertDialog
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import androidx.core.view.marginBottom
import androidx.core.view.marginEnd
import androidx.core.view.marginTop
import androidx.fragment.app.Fragment
import androidx.lifecycle.ViewModelProvider
import com.lizongying.mytv0.ModalFragment.Companion.KEY_URL
import com.lizongying.mytv0.SimpleServer.Companion.PORT
import com.lizongying.mytv0.databinding.SettingBinding
import kotlin.math.max
import kotlin.math.min


class SettingFragment : Fragment() {

    private var _binding: SettingBinding? = null
    private val binding get() = _binding!!

    private lateinit var uri: Uri

    private var server = "http://${PortUtil.lan()}:$PORT"

    private lateinit var viewModel: MainViewModel

    private var dialog: AlertDialog? = null

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View {
        val application = requireActivity().applicationContext as MyTVApplication
        val context = requireContext()
        val mainActivity = (activity as MainActivity)

        _binding = SettingBinding.inflate(inflater, container, false)

        binding.versionName.text = "v${context.appVersionName}"
        binding.version.text = REPO_URL

        val switchChannelReversal = _binding?.switchChannelReversal
        switchChannelReversal?.isChecked = SP.channelReversal
        switchChannelReversal?.setOnCheckedChangeListener { _, isChecked ->
            SP.channelReversal = isChecked
            mainActivity.settingActive()
        }

        val switchChannelNum = _binding?.switchChannelNum
        switchChannelNum?.isChecked = SP.channelNum
        switchChannelNum?.setOnCheckedChangeListener { _, isChecked ->
            SP.channelNum = isChecked
            mainActivity.settingActive()
        }

        val switchTime = _binding?.switchTime
        switchTime?.isChecked = SP.time
        switchTime?.setOnCheckedChangeListener { _, isChecked ->
            SP.time = isChecked
            mainActivity.settingActive()
        }

        val switchBootStartup = _binding?.switchBootStartup
        switchBootStartup?.isChecked = SP.bootStartup
        switchBootStartup?.setOnCheckedChangeListener { _, isChecked ->
            SP.bootStartup = isChecked
            mainActivity.settingActive()
        }

        val switchRepeatInfo = _binding?.switchRepeatInfo
        switchRepeatInfo?.isChecked = SP.repeatInfo
        switchRepeatInfo?.setOnCheckedChangeListener { _, isChecked ->
            SP.repeatInfo = isChecked
            mainActivity.settingActive()
        }

        val switchConfigAutoLoad = _binding?.switchConfigAutoLoad
        switchConfigAutoLoad?.isChecked = SP.configAutoLoad
        switchConfigAutoLoad?.setOnCheckedChangeListener { _, isChecked ->
            SP.configAutoLoad = isChecked
            mainActivity.settingActive()
        }

        val switchDefaultLike = _binding?.switchDefaultLike
        switchDefaultLike?.isChecked = SP.defaultLike
        switchDefaultLike?.setOnCheckedChangeListener { _, isChecked ->
            SP.defaultLike = isChecked
            mainActivity.settingActive()
        }

        val switchShowAllChannels = _binding?.switchShowAllChannels
        switchShowAllChannels?.isChecked = SP.showAllChannels

        val switchCompactMenu = _binding?.switchCompactMenu
        switchCompactMenu?.isChecked = SP.compactMenu
        switchCompactMenu?.setOnCheckedChangeListener { _, isChecked ->
            SP.compactMenu = isChecked
            mainActivity.updateMenuSize()
            mainActivity.settingActive()
        }

        val switchDisplaySeconds = _binding?.switchDisplaySeconds
        switchDisplaySeconds?.isChecked = SP.displaySeconds

        val switchSoftDecode = _binding?.switchSoftDecode
        switchSoftDecode?.isChecked = SP.softDecode
        switchSoftDecode?.setOnCheckedChangeListener { _, isChecked ->
            SP.softDecode = isChecked
            mainActivity.switchSoftDecode()
            mainActivity.settingActive()
        }

        binding.remoteSettings.setOnClickListener {
            val imageModalFragment = ModalFragment()
            val args = Bundle()
            args.putString(KEY_URL, "$server?${Utils.getDateTimestamp().toString().reversed()}")
            imageModalFragment.arguments = args

            imageModalFragment.show(requireFragmentManager(), ModalFragment.TAG)
            mainActivity.settingActive()
        }

        binding.checkVersion.setOnClickListener {
            try {
                startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(RELEASES_URL)))
            } catch (e: ActivityNotFoundException) {
                Log.w(TAG, "no browser, show qrcode", e)
                val imageModalFragment = ModalFragment()
                val args = Bundle()
                args.putString(KEY_URL, RELEASES_URL)
                imageModalFragment.arguments = args

                imageModalFragment.show(requireFragmentManager(), ModalFragment.TAG)
            }
            mainActivity.settingActive()
        }

        binding.confirmConfig.setOnClickListener {
            val sourcesFragment = SourcesFragment()

            sourcesFragment.show(requireFragmentManager(), SourcesFragment.TAG)
            mainActivity.settingActive()
        }

        binding.star.setOnClickListener {
            val imageModalFragment = ModalFragment()

            val args = Bundle()
            args.putString(KEY_URL, REPO_URL)
            imageModalFragment.arguments = args

            imageModalFragment.show(requireFragmentManager(), ModalFragment.TAG)
            mainActivity.settingActive()
        }

        binding.setting.setOnClickListener {
            hideSelf()
        }

        binding.exit.setOnClickListener {
            requireActivity().finishAffinity()
        }

        val txtTextSize =
            application.px2PxFont(binding.versionName.textSize)

        binding.content.layoutParams.width =
            application.px2Px(binding.content.layoutParams.width)
        binding.content.setPadding(
            application.px2Px(binding.content.paddingLeft),
            application.px2Px(binding.content.paddingTop),
            application.px2Px(binding.content.paddingRight),
            application.px2Px(binding.content.paddingBottom)
        )

        binding.name.textSize = application.px2PxFont(binding.name.textSize)
        binding.version.textSize = txtTextSize
        val layoutParamsVersion = binding.version.layoutParams as ViewGroup.MarginLayoutParams
        layoutParamsVersion.topMargin = application.px2Px(binding.version.marginTop)
        layoutParamsVersion.bottomMargin = application.px2Px(binding.version.marginBottom)
        binding.version.layoutParams = layoutParamsVersion

        val btnWidth =
            application.px2Px(binding.confirmConfig.layoutParams.width)

        val btnLayoutParams =
            binding.confirmConfig.layoutParams as ViewGroup.MarginLayoutParams
        btnLayoutParams.marginEnd = application.px2Px(binding.confirmConfig.marginEnd)

        binding.versionName.textSize = txtTextSize

        for (i in listOf(
            binding.remoteSettings,
            binding.confirmConfig,
            binding.clear,
            binding.checkVersion,
            binding.exit,
            binding.star,
        )) {
            i.layoutParams.width = btnWidth
            i.textSize = txtTextSize
            i.layoutParams = btnLayoutParams
            i.setOnFocusChangeListener { _, hasFocus ->
                if (hasFocus) {
                    i.background = ColorDrawable(
                        ContextCompat.getColor(
                            context,
                            R.color.focus
                        )
                    )
                    i.setTextColor(
                        ContextCompat.getColor(
                            context,
                            R.color.white
                        )
                    )
                } else {
                    i.background = ColorDrawable(
                        ContextCompat.getColor(
                            context,
                            R.color.description_blur
                        )
                    )
                    i.setTextColor(
                        ContextCompat.getColor(
                            context,
                            R.color.blur
                        )
                    )
                }
            }
        }

        val textSizeSwitch = application.px2PxFont(binding.switchChannelReversal.textSize)

        val layoutParamsSwitch =
            binding.switchChannelReversal.layoutParams as ViewGroup.MarginLayoutParams
        layoutParamsSwitch.topMargin =
            application.px2Px(binding.switchChannelReversal.marginTop)

        for (i in listOf(
            binding.switchChannelReversal,
            binding.switchChannelNum,
            binding.switchTime,
            binding.switchBootStartup,
            binding.switchRepeatInfo,
            binding.switchConfigAutoLoad,
            binding.switchDefaultLike,
            binding.switchShowAllChannels,
            binding.switchCompactMenu,
            binding.switchDisplaySeconds,
            binding.switchSoftDecode,
        )) {
            i.textSize = textSizeSwitch
            i.layoutParams = layoutParamsSwitch
            i.setOnFocusChangeListener { _, hasFocus ->
                if (hasFocus) {
                    i.setTextColor(
                        ContextCompat.getColor(
                            context,
                            R.color.focus
                        )
                    )
                } else {
                    i.setTextColor(
                        ContextCompat.getColor(
                            context,
                            R.color.title_blur
                        )
                    )
                }
            }
        }

        return binding.root
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)

        val context = requireActivity()
        val mainActivity = (activity as MainActivity)

        viewModel = ViewModelProvider(context)[MainViewModel::class.java]

        binding.switchDisplaySeconds.setOnCheckedChangeListener { _, isChecked ->
            viewModel.setDisplaySeconds(isChecked)
        }

        binding.clear.setOnClickListener {
            mainActivity.settingActive()
            dialog = AlertDialog.Builder(context)
                .setTitle(R.string.clear)
                .setItems(R.array.default_lists) { _, which ->
                    if (which == 0) restoreDefault() else switchToLite()
                }
                .setOnDismissListener { if (!isHidden) mainActivity.settingActive() }
                .show()
        }

        binding.switchShowAllChannels.setOnCheckedChangeListener { _, isChecked ->
            SP.showAllChannels = isChecked
            viewModel.groupModel.setChange()

            mainActivity.settingActive()
        }

        binding.remoteSettings.requestFocus()
    }

    private fun restoreDefault() {
        val context = requireActivity()
        val imageHelper = (context.applicationContext as MyTVApplication).imageHelper

        SP.channelNum = SP.DEFAULT_CHANNEL_NUM

        SP.sources = SP.DEFAULT_SOURCES
        Log.i(TAG, "DEFAULT_SOURCES ${SP.DEFAULT_SOURCES}")
        viewModel.sources.init()

        SP.channelReversal = SP.DEFAULT_CHANNEL_REVERSAL
        SP.time = SP.DEFAULT_TIME
        SP.bootStartup = SP.DEFAULT_BOOT_STARTUP
        SP.repeatInfo = SP.DEFAULT_REPEAT_INFO
        SP.configAutoLoad = SP.DEFAULT_CONFIG_AUTO_LOAD
        SP.proxy = SP.DEFAULT_PROXY

        imageHelper.clearImage()

        // TODO update player
        SP.softDecode = SP.DEFAULT_SOFT_DECODE

        SP.configUrl = SP.DEFAULT_CONFIG_URL
        Log.i(TAG, "config url: ${SP.configUrl}")
        context.deleteFile(CACHE_FILE_NAME)
        viewModel.reset(context)
        confirmConfig()

        SP.channel = SP.DEFAULT_CHANNEL
        Log.i(TAG, "default channel: ${SP.channel}")
        confirmChannel()

//            SP.positionGroup = SP.DEFAULT_POSITION_GROUP
//            viewModel.groupModel.setPosition(SP.DEFAULT_POSITION_GROUP)
//            viewModel.groupModel.setPositionPlaying(SP.DEFAULT_POSITION_GROUP)

        resetPosition()

        SP.showAllChannels = SP.DEFAULT_SHOW_ALL_CHANNELS
        SP.compactMenu = SP.DEFAULT_COMPACT_MENU

        viewModel.setDisplaySeconds(SP.DEFAULT_DISPLAY_SECONDS)

        SP.epg = SP.DEFAULT_EPG
        viewModel.updateEPG()

        R.string.config_restored.showToast()
    }

    private fun switchToLite() {
        SP.configUrl = SP.DEFAULT_CONFIG_URL
        // favourites are kept per list (SP.listKey), so switching keeps them
        viewModel.reset(requireContext(), R.raw.lite)
        resetPosition()
        viewModel.updateEPG()
        R.string.switched_to_lite.showToast()
    }

    private fun resetPosition() {
        SP.positionGroup = viewModel.groupModel.defaultPosition()
        viewModel.groupModel.initPosition()

        SP.position = SP.DEFAULT_POSITION
        Log.i(TAG, "list position: ${SP.position}")
        val tvListModel = viewModel.groupModel.getCurrentList()
        tvListModel?.setPosition(SP.DEFAULT_POSITION)
        tvListModel?.setPositionPlaying(SP.DEFAULT_POSITION)

        viewModel.groupModel.setPositionPlaying()
        viewModel.groupModel.getCurrentList()?.setPositionPlaying()
        viewModel.groupModel.getCurrent()?.setReady()
    }

    private fun confirmConfig() {
        if (SP.configUrl.isNullOrEmpty()) {
            Log.w(TAG, "SP.configUrl is null or empty")
            return
        }

        uri = Uri.parse(Utils.formatUrl(SP.configUrl!!))
        if (uri.scheme == "") {
            uri = uri.buildUpon().scheme("http").build()
        }
        if (uri.isAbsolute) {
            if (uri.scheme == "file") {
                requestReadPermissions()
            } else {
                viewModel.importFromUri(uri)
            }
        } else {
            R.string.invalid_config_address.showToast()
        }
        (activity as MainActivity).settingActive()
    }

    private fun confirmChannel() {
        SP.channel =
            min(max(SP.channel, 0), viewModel.groupModel.getAllList()!!.size())

        (activity as MainActivity).settingActive()
    }

    private fun hideSelf() {
        requireActivity().supportFragmentManager.beginTransaction()
            .hide(this)
            .commitAllowingStateLoss()
        (activity as MainActivity).showTimeFragment()
    }

    override fun onHiddenChanged(hidden: Boolean) {
        super.onHiddenChanged(hidden)
        if (hidden) {
            dialog?.dismiss()
        }
        if (_binding != null && !hidden) {
            binding.remoteSettings.requestFocus()
        }
    }

    private fun checkAndAddPermission(context: Context, permission: String, permissionsList: MutableList<String>) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M &&
            ContextCompat.checkSelfPermission(context, permission) != PackageManager.PERMISSION_GRANTED) {
            permissionsList.add(permission)
        }
    }

    private fun requestReadPermissions() {
        val context = requireContext()
        val permissionsList = mutableListOf<String>()

        checkAndAddPermission(context, Manifest.permission.READ_EXTERNAL_STORAGE, permissionsList)

        if (permissionsList.isNotEmpty()) {
            ActivityCompat.requestPermissions(
                requireActivity(),
                permissionsList.toTypedArray(),
                PERMISSION_READ_EXTERNAL_STORAGE_REQUEST_CODE
            )
        } else {
            viewModel.importFromUri(uri)
        }
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == PERMISSION_READ_EXTERNAL_STORAGE_REQUEST_CODE) {
            if (grantResults.isNotEmpty() && grantResults[0] == PackageManager.PERMISSION_GRANTED) {
                viewModel.importFromUri(uri)
            } else {
                R.string.authorization_failed.showToast()
            }
        }
    }

    override fun onDestroyView() {
        dialog?.dismiss()
        super.onDestroyView()
        _binding = null
    }

    companion object {
        const val TAG = "SettingFragment"
        const val REPO_URL = "https://github.com/lswang6/my-newtv"
        const val RELEASES_URL = "$REPO_URL/releases"
        const val PERMISSION_READ_EXTERNAL_STORAGE_REQUEST_CODE = 2
    }
}

